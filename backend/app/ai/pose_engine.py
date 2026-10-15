from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np

from mediapipe.tasks.python import vision


class PoseEngine:
    """
    EMPATH pose inference engine.

    Uses MediaPipe Tasks Pose Landmarker with the local
    lightweight pose model. The engine accepts OpenCV frames
    and returns structured pose information.

    This layer is deliberately independent from:
      - FastAPI
      - browser webcam handling
      - database persistence
      - event creation
      - alert generation

    That separation lets us test AI inference independently
    before connecting it to the operational pipeline.
    """

    MODEL_PATH = (
        Path(__file__).resolve().parent
        / "models"
        / "pose_landmarker_lite.task"
    )

    def __init__(
        self,
        model_path: str | Path | None = None,
        num_poses: int = 1,
        min_pose_detection_confidence: float = 0.5,
        min_pose_presence_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self.model_path = Path(model_path or self.MODEL_PATH)

        if not self.model_path.exists():
            raise FileNotFoundError(
                f"Pose model not found: {self.model_path}"
            )

        if num_poses < 1:
            raise ValueError("num_poses must be at least 1")

        self.num_poses = num_poses
        self.min_pose_detection_confidence = (
            min_pose_detection_confidence
        )
        self.min_pose_presence_confidence = (
            min_pose_presence_confidence
        )
        self.min_tracking_confidence = (
            min_tracking_confidence
        )

        self._landmarker: vision.PoseLandmarker | None = None

    def initialize(self) -> None:
        """Create the MediaPipe Pose Landmarker instance."""

        if self._landmarker is not None:
            return

        base_options = mp.tasks.BaseOptions(
            model_asset_path=str(self.model_path)
        )

        options = vision.PoseLandmarkerOptions(
            base_options=base_options,
            running_mode=mp.tasks.vision.RunningMode.IMAGE,
            num_poses=self.num_poses,
            min_pose_detection_confidence=(
                self.min_pose_detection_confidence
            ),
            min_pose_presence_confidence=(
                self.min_pose_presence_confidence
            ),
            min_tracking_confidence=(
                self.min_tracking_confidence
            ),
        )

        self._landmarker = (
            vision.PoseLandmarker.create_from_options(options)
        )

    def close(self) -> None:
        """Release MediaPipe resources."""

        if self._landmarker is not None:
            self._landmarker.close()
            self._landmarker = None

    def __enter__(self) -> "PoseEngine":
        self.initialize()
        return self

    def __exit__(
        self,
        exc_type: Any,
        exc_value: Any,
        traceback: Any,
    ) -> None:
        self.close()

    def detect(self, frame_bgr: np.ndarray) -> dict[str, Any]:
        """
        Run pose inference on one OpenCV BGR frame.

        Returns a compact serializable structure:

        {
            "pose_detected": bool,
            "pose_count": int,
            "poses": [
                {
                    "landmarks": [
                        {
                            "index": int,
                            "x": float,
                            "y": float,
                            "z": float,
                            "visibility": float | None,
                            "presence": float | None
                        }
                    ]
                }
            ]
        }
        """

        if self._landmarker is None:
            self.initialize()

        if frame_bgr is None:
            raise ValueError("frame_bgr cannot be None")

        if not isinstance(frame_bgr, np.ndarray):
            raise TypeError(
                "frame_bgr must be a NumPy ndarray"
            )

        if frame_bgr.ndim != 3:
            raise ValueError(
                "frame_bgr must be a 3-channel image"
            )

        if frame_bgr.shape[2] != 3:
            raise ValueError(
                "frame_bgr must have exactly 3 color channels"
            )

        # OpenCV uses BGR.
        # MediaPipe expects an RGB image for CPU inference.
        frame_rgb = cv2.cvtColor(
            frame_bgr,
            cv2.COLOR_BGR2RGB,
        )

        mp_image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=frame_rgb,
        )

        result = self._landmarker.detect(mp_image)

        poses: list[dict[str, Any]] = []

        for pose_landmarks in result.pose_landmarks:
            landmarks: list[dict[str, Any]] = []

            for index, landmark in enumerate(pose_landmarks):
                landmarks.append(
                    {
                        "index": index,
                        "x": float(landmark.x),
                        "y": float(landmark.y),
                        "z": float(landmark.z),
                        "visibility": (
                            float(landmark.visibility)
                            if landmark.visibility is not None
                            else None
                        ),
                        "presence": (
                            float(landmark.presence)
                            if landmark.presence is not None
                            else None
                        ),
                    }
                )

            poses.append(
                {
                    "landmarks": landmarks,
                }
            )

        return {
            "pose_detected": len(poses) > 0,
            "pose_count": len(poses),
            "poses": poses,
        }


def create_pose_engine() -> PoseEngine:
    """
    Factory used by the rest of EMPATH.

    Keeps model configuration in one place.
    """

    return PoseEngine(
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )