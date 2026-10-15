from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any
import time
import uuid

from sqlalchemy.orm import Session

from app.ai.behavior_analyzer import BehaviorAnalyzer
from app.ai.bed_movement_analyzer import BedMovementAnalyzer
from app.ai.event_bridge import AIEventBridge
from app.ai.pose_engine import PoseEngine

# A session becomes stale if no analyzed frame arrives within this window.
SESSION_IDLE_SECONDS = 20


def utc_now() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class LiveWebcamSession:
    camera_id: int
    started_by_user_id: int

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "starting"
    started_at: str = field(default_factory=utc_now)
    updated_at: str = field(default_factory=utc_now)

    # Monotonic time is used for timeout calculations.
    # UTC time is used for dashboard display.
    last_frame_at: float = field(default_factory=time.monotonic)
    last_frame_received_at: str | None = None

    pose_engine: Any = None
    behavior_analyzer: Any = None
    event_bridge: Any = None
    bed_movement_analyzer: Any = None

    lock: RLock = field(default_factory=RLock, repr=False)
    active: bool = True

    # Existing fall-analysis counters.
    frames_analyzed: int = 0
    pose_detected_frames: int = 0
    possible_fall_frames: int = 0
    events_created: int = 0
    alerts_created: int = 0

    # Experimental bed/body-movement metrics.
    # These counters do not create fall events or alerts.
    body_motion_frames: int = 0
    low_body_motion_frames: int = 0
    scene_change_frames: int = 0
    movement_unassessed_frames: int = 0
    movement_analyzer_errors: int = 0

    last_bed_movement: dict[str, Any] = field(
        default_factory=dict
    )

    # Existing latest-frame analysis information.
    last_confidence: float = 0.0
    last_posture: str = "UNKNOWN"
    last_reason: str = ""
    last_jpeg: bytes | None = None
    last_error: str | None = None


class LiveWebcamManager:
    """Manage in-memory browser-webcam analysis sessions.

    The browser submits frames to the backend.

    Existing pipeline:
        PoseEngine -> BehaviorAnalyzer -> AIEventBridge

    Additional experimental pipeline:
        Frame + pose result -> BedMovementAnalyzer

    Movement metrics are informational only. They do not independently
    generate fall events or emergency alerts.

    Sessions are process-local and do not survive a backend restart.
    """

    def __init__(self) -> None:
        self._sessions: dict[int, LiveWebcamSession] = {}
        self._lock = RLock()

    def start(
        self,
        *,
        camera_id: int,
        user_id: int,
    ) -> dict[str, Any]:
        """Start one analysis session for a camera."""

        with self._lock:
            old = self._sessions.get(camera_id)

            if old is not None and old.active:
                # Check idleness while holding the session lock.
                with old.lock:
                    if old.active:
                        idle_seconds = (
                            time.monotonic() - old.last_frame_at
                        )

                        if idle_seconds <= SESSION_IDLE_SECONDS:
                            raise ValueError(
                                "A live webcam session already exists "
                                "for this camera"
                            )

                        self._close_locked(
                            old,
                            final_status="stale",
                        )

            session = LiveWebcamSession(
                camera_id=camera_id,
                started_by_user_id=user_id,
            )

            engine: Any = None

            try:
                engine = PoseEngine()
                engine.initialize()

                session.pose_engine = engine
                session.behavior_analyzer = BehaviorAnalyzer()
                session.bed_movement_analyzer = BedMovementAnalyzer()
                session.event_bridge = AIEventBridge(
                    cooldown_seconds=10.0
                )

                session.status = "running"
                session.updated_at = utc_now()

                self._sessions[camera_id] = session

                return self._snapshot_locked(session)

            except Exception as error:
                # Retain startup failure information for troubleshooting.
                if engine is not None:
                    try:
                        engine.close()
                    except Exception:
                        pass

                session.pose_engine = None
                session.behavior_analyzer = None
                session.bed_movement_analyzer = None
                session.event_bridge = None

                session.active = False
                session.status = "error"
                session.last_error = (
                    f"{type(error).__name__}: {error}"
                )
                session.updated_at = utc_now()

                self._sessions[camera_id] = session
                raise

    def _close_locked(
        self,
        session: LiveWebcamSession,
        *,
        final_status: str = "stopped",
        error_message: str | None = None,
    ) -> None:
        """Stop a session and release AI resources."""

        with session.lock:
            if not session.active:
                return

            session.active = False
            session.status = final_status
            session.updated_at = utc_now()

            if final_status == "error":
                session.last_error = (
                    error_message
                    or session.last_error
                    or "Unknown processing error"
                )

            pose_engine = session.pose_engine

            # Detach resources before attempting cleanup.
            session.pose_engine = None
            session.behavior_analyzer = None
            session.bed_movement_analyzer = None
            session.event_bridge = None

            if pose_engine is not None:
                try:
                    pose_engine.close()
                except Exception:
                    # Preserve the session status if cleanup itself fails.
                    pass

    def stop(
        self,
        *,
        camera_id: int,
    ) -> dict[str, Any]:
        """Intentionally stop an active session."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if session is None or not session.active:
                raise ValueError(
                    "No active live webcam session exists for this camera"
                )

            self._close_locked(
                session,
                final_status="stopped",
            )

            return self._snapshot_locked(session)

    def _get_active_session(
        self,
        camera_id: int,
    ) -> LiveWebcamSession | None:
        """Return the session and expire it if it becomes idle."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if session is None:
                return None

            with session.lock:
                if (
                    session.active
                    and time.monotonic() - session.last_frame_at
                    > SESSION_IDLE_SECONDS
                ):
                    self._close_locked(
                        session,
                        final_status="stale",
                    )

            return session

    def status(
        self,
        *,
        camera_id: int,
    ) -> dict[str, Any]:
        """Return current status, expiring an idle session if necessary."""

        with self._lock:
            session = self._sessions.get(camera_id)

            if session is None:
                return {
                    "camera_id": camera_id,
                    "session_id": None,
                    "status": "stopped",
                    "health_status": "stopped",
                    "active": False,
                    "started_by_user_id": None,
                    "started_at": None,
                    "updated_at": None,
                    "last_frame_received_at": None,
                    "last_frame_age_seconds": None,
                    "stale_after_seconds": SESSION_IDLE_SECONDS,
                    "frames_analyzed": 0,
                    "pose_detected_frames": 0,
                    "pose_detection_rate": 0.0,
                    "possible_fall_frames": 0,
                    "body_motion_frames": 0,
                    "low_body_motion_frames": 0,
                    "scene_change_frames": 0,
                    "movement_unassessed_frames": 0,
                    "movement_analyzer_errors": 0,
                    "last_bed_movement": {},
                    "events_created": 0,
                    "alerts_created": 0,
                    "last_posture": "UNKNOWN",
                    "last_confidence": 0.0,
                    "last_reason": "",
                    "last_error": None,
                }

            with session.lock:
                if (
                    session.active
                    and time.monotonic() - session.last_frame_at
                    > SESSION_IDLE_SECONDS
                ):
                    self._close_locked(
                        session,
                        final_status="stale",
                    )

            return self._snapshot_locked(session)

    def _snapshot_locked(
        self,
        session: LiveWebcamSession,
    ) -> dict[str, Any]:
        """Build a consistent response containing session and movement metrics."""

        with session.lock:
            pose_rate = (
                session.pose_detected_frames / session.frames_analyzed
                if session.frames_analyzed
                else 0.0
            )

            frame_age_seconds = (
                round(
                    max(
                        0.0,
                        time.monotonic() - session.last_frame_at,
                    ),
                    1,
                )
                if session.last_frame_received_at is not None
                else None
            )

            # Derive health from actual session state.
            if session.status == "error" or session.last_error:
                health_status = "error"
            elif session.status == "stale":
                health_status = "stale"
            elif not session.active or session.status == "stopped":
                health_status = "stopped"
            elif session.frames_analyzed == 0:
                health_status = "starting"
            elif (
                frame_age_seconds is not None
                and frame_age_seconds > SESSION_IDLE_SECONDS
            ):
                health_status = "stale"
            else:
                health_status = "live"

            return {
                "camera_id": session.camera_id,
                "session_id": session.session_id,
                "status": session.status,
                "health_status": health_status,
                "active": session.active,
                "started_by_user_id": session.started_by_user_id,
                "started_at": session.started_at,
                "updated_at": session.updated_at,
                "last_frame_received_at": (
                    session.last_frame_received_at
                ),
                "last_frame_age_seconds": frame_age_seconds,
                "stale_after_seconds": SESSION_IDLE_SECONDS,

                # Existing metrics.
                "frames_analyzed": session.frames_analyzed,
                "pose_detected_frames": session.pose_detected_frames,
                "pose_detection_rate": round(pose_rate, 4),
                "possible_fall_frames": session.possible_fall_frames,
                "events_created": session.events_created,
                "alerts_created": session.alerts_created,

                # Additional experimental movement metrics.
                "body_motion_frames": session.body_motion_frames,
                "low_body_motion_frames": (
                    session.low_body_motion_frames
                ),
                "scene_change_frames": session.scene_change_frames,
                "movement_unassessed_frames": (
                    session.movement_unassessed_frames
                ),
                "movement_analyzer_errors": (
                    session.movement_analyzer_errors
                ),
                "last_bed_movement": dict(
                    session.last_bed_movement
                ),

                # Existing latest behavioral result.
                "last_posture": session.last_posture,
                "last_confidence": session.last_confidence,
                "last_reason": session.last_reason,
                "last_error": session.last_error,
            }

    def process_frame(
        self,
        *,
        camera_id: int,
        user_id: int,
        frame: Any,
        jpeg_bytes: bytes,
        db: Session,
    ) -> dict[str, Any]:
        """Analyze a frame and update session, fall, and movement metrics."""

        session = self._get_active_session(camera_id)

        if session is None:
            raise ValueError(
                "No active live webcam session. Start it first."
            )

        with session.lock:
            if not session.active:
                raise ValueError(
                    "The live webcam session has stopped"
                )

            if session.started_by_user_id != user_id:
                raise PermissionError(
                    "Only the Admin who started this session "
                    "can submit frames"
                )

            try:
                # ADDED: Capture when this frame enters backend analysis.
                # This is not the camera-side capture timestamp.
                frame_received_at_utc = utc_now()

                # Main existing AI pipeline.
                pose_result = session.pose_engine.detect(frame)

                behavior = session.behavior_analyzer.analyze(
                    pose_result
                )

                # Additional movement analysis.
                #
                # This is intentionally isolated: movement analyzer errors
                # must not stop the existing fall-analysis pipeline.
                # Movement metrics do not independently create alerts.
                try:
                    bed_movement = (
                        session.bed_movement_analyzer.update(
                            frame,
                            pose_result,
                        )
                    )

                    session.last_bed_movement = bed_movement

                    if (
                        bed_movement.get("body_motion_detected")
                        is True
                    ):
                        session.body_motion_frames += 1

                    elif (
                        bed_movement.get("pose_landmarks_visible")
                        is True
                        and bed_movement.get("body_motion_detected")
                        is False
                    ):
                        session.low_body_motion_frames += 1

                    if bed_movement.get("scene_change_detected"):
                        session.scene_change_frames += 1

                    if not bed_movement.get(
                        "pose_landmarks_visible",
                        False,
                    ):
                        session.movement_unassessed_frames += 1

                except Exception as movement_error:
                    # Keep the fall detector running if the experimental
                    # movement analyzer fails for an individual frame.
                    session.movement_analyzer_errors += 1
                    session.movement_unassessed_frames += 1

                    session.last_bed_movement = {
                        "pose_landmarks_visible": False,
                        "tracked_joints": 0,
                        "body_motion_score": None,
                        "body_motion_detected": None,
                        "scene_change_pct": None,
                        "scene_change_detected": False,
                        "status": "MOVEMENT ANALYZER ERROR",
                        "experimental": True,
                        "medical_assessment": False,
                        "error": (
                            f"{type(movement_error).__name__}: "
                            f"{movement_error}"
                        ),
                    }

                # Existing fall/session counters.
                session.frames_analyzed += 1

                if bool(
                    getattr(behavior, "pose_detected", False)
                ):
                    session.pose_detected_frames += 1

                if bool(
                    getattr(behavior, "possible_fall", False)
                ):
                    session.possible_fall_frames += 1

                session.last_confidence = float(
                    getattr(behavior, "confidence", 0.0) or 0.0
                )

                session.last_posture = str(
                    getattr(behavior, "posture", "UNKNOWN")
                    or "UNKNOWN"
                )

                session.last_reason = str(
                    getattr(behavior, "reason", "") or ""
                )

                # Update the latest successfully analyzed frame.
                session.last_jpeg = jpeg_bytes
                session.last_frame_at = time.monotonic()

                # ADDED: Reuse the same timestamp for session status.
                session.last_frame_received_at = frame_received_at_utc
                session.updated_at = session.last_frame_received_at

                session.status = "running"
                session.last_error = None

                # Keep existing fall-event/alert behavior unchanged.
                # Only BehaviorAnalyzer results are passed to this bridge.
                bridge_result = session.event_bridge.process(
                    db,
                    behavior,
                    camera_id=camera_id,
                    patient_id=None,
                    extra_metadata={
                        "analysis_mode": "browser_webcam_live",
                        "live_session_id": session.session_id,
                        "submitted_by_user_id": user_id,
                        "frame_number": session.frames_analyzed,

                        # ADDED: UTC timestamp included in event metadata.
                        "frame_received_at_utc": frame_received_at_utc,
                    },
                )

                created = None

                if bridge_result:
                    event = bridge_result["event"]
                    alert = bridge_result["alert"]

                    session.events_created += 1
                    session.alerts_created += 1

                    created = {
                        "event_id": getattr(event, "id", None),
                        "alert_id": getattr(alert, "id", None),
                    }

                response = self._snapshot_locked(session)
                response["new_event_alert"] = created

                return response

            except Exception as error:
                # Preserve the existing behavior for genuine fall-pipeline
                # or event-pipeline failures.
                if session.active:
                    message = (
                        f"{type(error).__name__}: {error}"
                    )

                    self._close_locked(
                        session,
                        final_status="error",
                        error_message=message,
                    )

                raise

    def latest_jpeg(
        self,
        *,
        camera_id: int,
    ) -> bytes | None:
        """Return the latest analyzed JPEG only while the session is active."""

        session = self._get_active_session(camera_id)

        if session is None:
            return None

        with session.lock:
            if not session.active:
                return None

            return session.last_jpeg


live_webcam_manager = LiveWebcamManager()