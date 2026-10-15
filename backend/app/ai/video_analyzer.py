from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2

from app.ai.behavior_analyzer import BehaviorAnalyzer
from app.ai.bed_movement_analyzer import BedMovementAnalyzer
from app.ai.pose_engine import PoseEngine


class VideoAnalyzer:
    """
    EMPATH video analysis pipeline.

    Existing pipeline:
        OpenCV -> PoseEngine -> BehaviorAnalyzer

    Additional experimental pipeline:
        Video frame + pose result -> BedMovementAnalyzer

    Bed movement indicators do not independently create
    fall events or emergency alerts.
    """

    def __init__(
        self,
        *,
        sample_every_n_frames: int = 1,
        max_frames: int | None = None,
    ) -> None:
        if sample_every_n_frames < 1:
            raise ValueError(
                "sample_every_n_frames must be >= 1"
            )

        self.sample_every_n_frames = sample_every_n_frames
        self.max_frames = max_frames

    def analyze(
        self,
        video_path: str | Path,
    ) -> dict[str, Any]:
        video_path = Path(video_path)

        if not video_path.exists():
            raise FileNotFoundError(
                f"Video file does not exist: {video_path}"
            )

        capture = cv2.VideoCapture(str(video_path))

        if not capture.isOpened():
            capture.release()
            raise RuntimeError(
                f"Unable to open video: {video_path}"
            )

        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(
            capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        )
        width = int(
            capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0
        )
        height = int(
            capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0
        )

        duration_seconds = (
            frame_count / fps
            if fps > 0
            else 0.0
        )

        pose_engine = PoseEngine()
        behavior_analyzer = BehaviorAnalyzer()
        bed_movement_analyzer = BedMovementAnalyzer()

        results: list[dict[str, Any]] = []

        frames_read = 0
        frames_analyzed = 0
        pose_detected_frames = 0
        possible_fall_frames = 0

        body_motion_frames = 0
        low_body_motion_frames = 0
        scene_change_frames = 0
        movement_unassessed_frames = 0

        try:
            pose_engine.initialize()

            while True:
                success, frame = capture.read()

                if not success:
                    break

                frames_read += 1

                if (
                    self.max_frames is not None
                    and frames_read > self.max_frames
                ):
                    break

                if (
                    (frames_read - 1)
                    % self.sample_every_n_frames
                    != 0
                ):
                    continue

                # Existing pose and fall analysis.
                pose_result = pose_engine.detect(frame)

                behavior_result = behavior_analyzer.analyze(
                    pose_result
                )

                # Additional experimental movement analysis.
                # Uses the same frame and pose result, so another
                # pose model does not need to be loaded.
                bed_movement_result = (
                    bed_movement_analyzer.update(
                        frame,
                        pose_result,
                    )
                )

                frames_analyzed += 1

                if behavior_result.pose_detected:
                    pose_detected_frames += 1

                if behavior_result.possible_fall:
                    possible_fall_frames += 1

                if bed_movement_result[
                    "body_motion_detected"
                ] is True:
                    body_motion_frames += 1

                elif (
                    bed_movement_result[
                        "pose_landmarks_visible"
                    ]
                    and bed_movement_result[
                        "body_motion_detected"
                    ] is False
                ):
                    low_body_motion_frames += 1

                if bed_movement_result[
                    "scene_change_detected"
                ]:
                    scene_change_frames += 1

                if not bed_movement_result[
                    "pose_landmarks_visible"
                ]:
                    movement_unassessed_frames += 1

                timestamp_seconds = (
                    (frames_read - 1) / fps
                    if fps > 0
                    else 0.0
                )

                behavior_data = asdict(behavior_result)

                results.append(
                    {
                        "frame_number": frames_read,
                        "timestamp_seconds": round(
                            timestamp_seconds,
                            3,
                        ),
                        **behavior_data,
                        "bed_movement": bed_movement_result,
                    }
                )

        finally:
            capture.release()
            pose_engine.close()

        pose_detection_rate = (
            pose_detected_frames / frames_analyzed
            if frames_analyzed > 0
            else 0.0
        )

        return {
            "video": {
                "filename": video_path.name,
                "width": width,
                "height": height,
                "fps": round(fps, 2),
                "frame_count": frame_count,
                "duration_seconds": round(
                    duration_seconds,
                    2,
                ),
            },
            "analysis": {
                "frames_read": frames_read,
                "frames_analyzed": frames_analyzed,
                "sample_every_n_frames": (
                    self.sample_every_n_frames
                ),
                "pose_detected_frames": (
                    pose_detected_frames
                ),
                "pose_detection_rate": round(
                    pose_detection_rate,
                    4,
                ),
                "possible_fall_frames": (
                    possible_fall_frames
                ),
                "bed_movement": {
                    "body_motion_frames": body_motion_frames,
                    "low_body_motion_frames": (
                        low_body_motion_frames
                    ),
                    "scene_change_frames": scene_change_frames,
                    "movement_unassessed_frames": (
                        movement_unassessed_frames
                    ),
                    "experimental": True,
                    "note": (
                        "Visual movement indicators only. "
                        "Scene changes may be caused by lighting, "
                        "blankets, camera movement, or compression. "
                        "These metrics are not a medical assessment."
                    ),
                },
            },
            "results": results,
        }