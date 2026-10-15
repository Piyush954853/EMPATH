
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, RLock, Thread
from types import SimpleNamespace
import time
from typing import Any

from app.ai.event_bridge import AIEventBridge
from app.ai.video_analyzer import VideoAnalyzer
from app.core.database import SessionLocal


BUSY_STATUSES = {"starting", "running", "stopping"}
VISIBLE_STATUSES = {"starting", "running", "stopping"}


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def safe_int(value: Any, default: int = 0) -> int:
    """Convert a value to an integer without crashing on bad data."""
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Convert a value to a float without crashing on bad data."""
    try:
        return float(value)
    except (TypeError, ValueError, OverflowError):
        return default


@dataclass
class PlaybackSession:
    camera_id: int
    video_path: Path
    original_filename: str

    status: str = "starting"
    started_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    stop_event: Event = field(default_factory=Event)
    thread: Thread | None = None

    # Existing playback metrics.
    loops_completed: int = 0
    frames_analyzed_total: int = 0
    last_frames_analyzed: int = 0
    last_pose_detection_rate: float = 0.0
    last_possible_fall_frames: int = 0

    events_created: int = 0
    alerts_created: int = 0

    # Experimental movement totals across completed loops.
    body_motion_frames: int = 0
    low_body_motion_frames: int = 0
    scene_change_frames: int = 0
    movement_unassessed_frames: int = 0

    # Movement metrics from the most recently completed loop.
    last_body_motion_frames: int = 0
    last_low_body_motion_frames: int = 0
    last_scene_change_frames: int = 0
    last_movement_unassessed_frames: int = 0

    # Latest per-frame movement information.
    last_bed_movement: dict[str, Any] = field(
        default_factory=dict
    )

    bed_movement_note: str = (
        "Experimental visual movement indicators only; "
        "not a medical assessment."
    )

    last_error: str | None = None


class PlaybackManager:
    """
    Single-process shared playback manager for the EMPATH prototype.

    Existing pipeline:
        VideoAnalyzer -> BehaviorAnalyzer results -> AIEventBridge

    Additional pipeline:
        VideoAnalyzer movement metrics -> PlaybackSession status

    Movement metrics are informational and do not independently
    generate fall events or alerts.

    Session state is in memory and resets after a backend restart.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, PlaybackSession] = {}
        self._lock = RLock()

    def is_busy(self, camera_id: int) -> bool:
        with self._lock:
            session = self._sessions.get(camera_id)
            return bool(
                session and session.status in BUSY_STATUSES
            )

    def start(
        self,
        *,
        camera_id: int,
        video_path: Path,
        original_filename: str,
    ) -> dict[str, Any]:
        """Start a shared playback session for a camera."""

        video_path = Path(video_path)

        if not video_path.is_file():
            raise ValueError(
                f"Playback video does not exist: {video_path}"
            )

        with self._lock:
            previous = self._sessions.get(camera_id)

            if previous and previous.status in BUSY_STATUSES:
                raise ValueError(
                    "A playback session is already active for this camera"
                )

            session = PlaybackSession(
                camera_id=camera_id,
                video_path=video_path,
                original_filename=original_filename,
            )

            self._sessions[camera_id] = session

            worker = Thread(
                target=self._run_session,
                args=(session,),
                name=f"empath-playback-camera-{camera_id}",
                daemon=True,
            )

            session.thread = worker
            worker.start()

            return self._snapshot_locked(session)

    def stop(self, camera_id: int) -> dict[str, Any]:
        """Request that an active playback session stop."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if session is None:
                raise ValueError(
                    "No playback session exists for this camera"
                )

            if session.status in {"stopped", "error"}:
                raise ValueError(
                    "There is no active playback session to stop"
                )

            session.stop_event.set()
            session.status = "stopping"
            session.updated_at = utc_now()

            return self._snapshot_locked(session)

    def get_status(self, camera_id: int) -> dict[str, Any]:
        """Return playback status and movement metrics."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if session is None:
                return {
                    "camera_id": camera_id,
                    "status": "stopped",
                    "active": False,
                    "busy": False,
                    "video_available": False,
                    "original_filename": None,
                    "started_at": None,
                    "updated_at": None,
                    "loops_completed": 0,
                    "frames_analyzed_total": 0,
                    "last_frames_analyzed": 0,
                    "last_pose_detection_rate": 0.0,
                    "last_possible_fall_frames": 0,
                    "events_created": 0,
                    "alerts_created": 0,
                    "body_motion_frames": 0,
                    "low_body_motion_frames": 0,
                    "scene_change_frames": 0,
                    "movement_unassessed_frames": 0,
                    "last_body_motion_frames": 0,
                    "last_low_body_motion_frames": 0,
                    "last_scene_change_frames": 0,
                    "last_movement_unassessed_frames": 0,
                    "last_bed_movement": {},
                    "bed_movement_note": (
                        "Experimental visual movement indicators only; "
                        "not a medical assessment."
                    ),
                    "last_error": None,
                }

            return self._snapshot_locked(session)

    def get_video_path(self, camera_id: int) -> Path | None:
        """Return the video path while playback is visible."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if (
                session is None
                or session.status not in VISIBLE_STATUSES
                or not session.video_path.is_file()
            ):
                return None

            return session.video_path

    def _snapshot_locked(
        self,
        session: PlaybackSession,
    ) -> dict[str, Any]:
        """Build the status response for APIs and the dashboard."""

        return {
            "camera_id": session.camera_id,
            "status": session.status,
            "active": session.status in {"starting", "running"},
            "busy": session.status in BUSY_STATUSES,
            "video_available": (
                session.status in VISIBLE_STATUSES
                and session.video_path.is_file()
            ),
            "original_filename": session.original_filename,
            "started_at": session.started_at,
            "updated_at": session.updated_at,
            "loops_completed": session.loops_completed,
            "frames_analyzed_total": session.frames_analyzed_total,
            "last_frames_analyzed": session.last_frames_analyzed,
            "last_pose_detection_rate": (
                session.last_pose_detection_rate
            ),
            "last_possible_fall_frames": (
                session.last_possible_fall_frames
            ),
            "events_created": session.events_created,
            "alerts_created": session.alerts_created,

            # Cumulative movement counters.
            "body_motion_frames": session.body_motion_frames,
            "low_body_motion_frames": (
                session.low_body_motion_frames
            ),
            "scene_change_frames": session.scene_change_frames,
            "movement_unassessed_frames": (
                session.movement_unassessed_frames
            ),

            # Counters from the most recently completed loop.
            "last_body_motion_frames": (
                session.last_body_motion_frames
            ),
            "last_low_body_motion_frames": (
                session.last_low_body_motion_frames
            ),
            "last_scene_change_frames": (
                session.last_scene_change_frames
            ),
            "last_movement_unassessed_frames": (
                session.last_movement_unassessed_frames
            ),

            "last_bed_movement": dict(
                session.last_bed_movement
            ),
            "bed_movement_note": session.bed_movement_note,
            "last_error": session.last_error,
        }

    def _set_status(
        self,
        session: PlaybackSession,
        status_value: str,
        error: str | None = None,
    ) -> None:
        with self._lock:
            if self._sessions.get(session.camera_id) is not session:
                return

            session.status = status_value
            session.last_error = error
            session.updated_at = utc_now()

    def _record_completed_loop(
        self,
        session: PlaybackSession,
        *,
        frames_analyzed: int,
        pose_detection_rate: float,
        possible_fall_frames: int,
        events_created: int,
        alerts_created: int,
        body_motion_frames: int = 0,
        low_body_motion_frames: int = 0,
        scene_change_frames: int = 0,
        movement_unassessed_frames: int = 0,
        last_bed_movement: dict[str, Any] | None = None,
        bed_movement_note: str | None = None,
    ) -> None:
        """Persist the counters for one completed playback loop."""

        with self._lock:
            if self._sessions.get(session.camera_id) is not session:
                return

            session.loops_completed += 1
            session.frames_analyzed_total += frames_analyzed
            session.last_frames_analyzed = frames_analyzed
            session.last_pose_detection_rate = pose_detection_rate
            session.last_possible_fall_frames = possible_fall_frames

            session.events_created += events_created
            session.alerts_created += alerts_created

            # Cumulative movement metrics.
            session.body_motion_frames += body_motion_frames
            session.low_body_motion_frames += (
                low_body_motion_frames
            )
            session.scene_change_frames += scene_change_frames
            session.movement_unassessed_frames += (
                movement_unassessed_frames
            )

            # Latest completed loop metrics.
            session.last_body_motion_frames = body_motion_frames
            session.last_low_body_motion_frames = (
                low_body_motion_frames
            )
            session.last_scene_change_frames = scene_change_frames
            session.last_movement_unassessed_frames = (
                movement_unassessed_frames
            )

            if last_bed_movement is not None:
                session.last_bed_movement = dict(
                    last_bed_movement
                )

            if bed_movement_note:
                session.bed_movement_note = bed_movement_note

            session.updated_at = utc_now()

    def _run_session(self, session: PlaybackSession) -> None:
        """Run repeated video analysis and update fall/movement metrics."""

        bridge = AIEventBridge(cooldown_seconds=10.0)
        failure: str | None = None

        try:
            while not session.stop_event.is_set():
                loop_started = time.monotonic()
                self._set_status(session, "running")

                analyzer = VideoAnalyzer(
                    sample_every_n_frames=1,
                )

                result = analyzer.analyze(session.video_path)

                # Do not create events from a pass that was stopped.
                if session.stop_event.is_set():
                    break

                analysis = result.get("analysis", {})
                frame_results = result.get("results", [])

                loop_number = (
                    self.get_status(session.camera_id)["loops_completed"]
                    + 1
                )

                events_this_loop = 0
                alerts_this_loop = 0

                # VideoAnalyzer provides movement counters for this loop.
                movement_analysis = (
                    analysis.get("bed_movement") or {}
                )

                body_motion_this_loop = safe_int(
                    movement_analysis.get("body_motion_frames")
                )
                low_motion_this_loop = safe_int(
                    movement_analysis.get("low_body_motion_frames")
                )
                scene_change_this_loop = safe_int(
                    movement_analysis.get("scene_change_frames")
                )
                unassessed_this_loop = safe_int(
                    movement_analysis.get(
                        "movement_unassessed_frames"
                    )
                )

                # Capture the latest per-frame movement result for the UI.
                last_bed_movement: dict[str, Any] = {}

                for frame_result in reversed(frame_results):
                    if not isinstance(frame_result, dict):
                        continue

                    movement = frame_result.get("bed_movement")

                    if isinstance(movement, dict):
                        last_bed_movement = movement
                        break

                movement_note = movement_analysis.get("note")
                if not isinstance(movement_note, str):
                    movement_note = (
                        "Experimental visual movement indicators only; "
                        "not a medical assessment."
                    )

                with SessionLocal() as db:
                    for frame_result in frame_results:
                        if session.stop_event.is_set():
                            break

                        if not isinstance(frame_result, dict):
                            continue

                        # Keep the established fall-analysis contract.
                        # Bed movement is not passed as an independent
                        # trigger into AIEventBridge.
                        behavior = SimpleNamespace(
                            possible_fall=bool(
                                frame_result.get(
                                    "possible_fall",
                                    False,
                                )
                            ),
                            posture=frame_result.get(
                                "posture",
                                "UNKNOWN",
                            ),
                            movement_score=frame_result.get(
                                "movement_score",
                                0.0,
                            ),
                            body_angle=frame_result.get(
                                "body_angle",
                                0.0,
                            ),
                            confidence=frame_result.get(
                                "confidence",
                                0.0,
                            ),
                            reason=frame_result.get(
                                "reason",
                                (
                                    "Possible visual safety event "
                                    "requires review."
                                ),
                            ),
                        )

                        bridge_result = bridge.process(
                            db,
                            behavior,
                            camera_id=session.camera_id,
                            patient_id=None,
                            extra_metadata={
                                "analysis_mode": "shared_loop_playback",
                                "video_filename": (
                                    session.original_filename
                                ),
                                "playback_loop": loop_number,
                                "frame_number": frame_result.get(
                                    "frame_number"
                                ),
                                "timestamp_seconds": (
                                    frame_result.get(
                                        "timestamp_seconds"
                                    )
                                ),
                            },
                        )

                        if bridge_result:
                            events_this_loop += 1
                            alerts_this_loop += 1

                if session.stop_event.is_set():
                    break

                self._record_completed_loop(
                    session,
                    frames_analyzed=safe_int(
                        analysis.get("frames_analyzed")
                    ),
                    pose_detection_rate=safe_float(
                        analysis.get("pose_detection_rate")
                    ),
                    possible_fall_frames=safe_int(
                        analysis.get("possible_fall_frames")
                    ),
                    events_created=events_this_loop,
                    alerts_created=alerts_this_loop,
                    body_motion_frames=body_motion_this_loop,
                    low_body_motion_frames=low_motion_this_loop,
                    scene_change_frames=scene_change_this_loop,
                    movement_unassessed_frames=unassessed_this_loop,
                    last_bed_movement=last_bed_movement,
                    bed_movement_note=movement_note,
                )

                # Pace the worker approximately to the video's duration.
                # AI analysis itself may take longer than real time.
                duration = safe_float(
                    (result.get("video") or {}).get(
                        "duration_seconds"
                    )
                )

                elapsed = time.monotonic() - loop_started
                remaining = max(0.0, duration - elapsed)

                if remaining > 0:
                    session.stop_event.wait(remaining)

        except Exception as exc:
            failure = f"{type(exc).__name__}: {exc}"

            self._set_status(
                session,
                "error",
                error=failure,
            )

        finally:
            # Preserve the existing playback cleanup behavior:
            # playback worker removes its temporary stored video on exit.
            try:
                session.video_path.unlink(missing_ok=True)
            except OSError:
                pass

            with self._lock:
                if self._sessions.get(session.camera_id) is session:
                    if failure is None:
                        session.status = "stopped"
                        session.last_error = None

                    session.updated_at = utc_now()


playback_manager = PlaybackManager()
