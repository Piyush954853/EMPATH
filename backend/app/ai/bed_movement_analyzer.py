from __future__ import annotations

from collections import deque
from math import hypot
from typing import Any

import cv2
import numpy as np


# MediaPipe landmarks:
# shoulders, elbows, wrists, hips, knees, ankles
_TRACKED_JOINTS = (
    11, 12,
    13, 14,
    15, 16,
    23, 24,
    25, 26,
    27, 28,
)


class BedMovementAnalyzer:
    """
    Experimental visual movement monitor for EMPATH.

    Tracks visible body-joint movement when sufficient
    pose landmarks are available.

    When landmarks are unavailable, reports scene changes
    separately. Scene changes are not attributed to the patient.

    This is not a medical diagnostic or emergency detector.
    """

    def __init__(
        self,
        *,
        joint_motion_threshold: float = 0.025,
        scene_change_threshold_pct: float = 0.5,
        history_size: int = 5,
    ) -> None:
        self.joint_motion_threshold = float(
            joint_motion_threshold
        )
        self.scene_change_threshold_pct = float(
            scene_change_threshold_pct
        )

        self._previous_joints: dict[
            int, tuple[float, float]
        ] = {}

        self._previous_gray: np.ndarray | None = None

        self._movement_history: deque[bool] = deque(
            maxlen=history_size
        )

    @staticmethod
    def _landmark_map(
        pose_result: dict[str, Any],
    ) -> dict[int, tuple[float, float]]:
        poses = pose_result.get("poses") or []

        if not poses:
            return {}

        landmarks = poses[0].get("landmarks") or []
        result = {}

        for index in _TRACKED_JOINTS:
            if index >= len(landmarks):
                continue

            landmark = landmarks[index]

            confidence_values = [
                float(value)
                for value in (
                    landmark.get("visibility"),
                    landmark.get("presence"),
                )
                if value is not None
            ]

            if (
                confidence_values
                and min(confidence_values) < 0.4
            ):
                continue

            result[index] = (
                float(landmark["x"]),
                float(landmark["y"]),
            )

        return result

    @staticmethod
    def _normalizing_scale(
        joints: dict[int, tuple[float, float]],
    ) -> float:
        shoulders = [
            joints[i] for i in (11, 12) if i in joints
        ]

        hips = [
            joints[i] for i in (23, 24) if i in joints
        ]

        if len(shoulders) == 2 and len(hips) == 2:
            shoulder_center = (
                (shoulders[0][0] + shoulders[1][0]) / 2,
                (shoulders[0][1] + shoulders[1][1]) / 2,
            )

            hip_center = (
                (hips[0][0] + hips[1][0]) / 2,
                (hips[0][1] + hips[1][1]) / 2,
            )

            torso_size = hypot(
                shoulder_center[0] - hip_center[0],
                shoulder_center[1] - hip_center[1],
            )

            if torso_size >= 0.035:
                return torso_size

        if len(joints) >= 2:
            xs = [point[0] for point in joints.values()]
            ys = [point[1] for point in joints.values()]

            diagonal = hypot(
                max(xs) - min(xs),
                max(ys) - min(ys),
            )

            if diagonal >= 0.05:
                return diagonal

        return 0.0

    def _scene_change(
        self,
        frame: np.ndarray,
    ) -> tuple[float | None, bool]:
        gray = cv2.cvtColor(
            frame,
            cv2.COLOR_BGR2GRAY,
        )

        gray = cv2.resize(
            gray,
            (160, 90),
            interpolation=cv2.INTER_AREA,
        )

        gray = cv2.GaussianBlur(
            gray,
            (5, 5),
            0,
        )

        previous = self._previous_gray
        self._previous_gray = gray

        if previous is None:
            return None, False

        difference = cv2.absdiff(gray, previous)

        _, changed = cv2.threshold(
            difference,
            20,
            255,
            cv2.THRESH_BINARY,
        )

        changed_pct = (
            100.0
            * float(cv2.countNonZero(changed))
            / float(changed.size)
        )

        return (
            changed_pct,
            changed_pct >= self.scene_change_threshold_pct,
        )

    def update(
        self,
        frame: np.ndarray,
        pose_result: dict[str, Any],
    ) -> dict[str, Any]:
        scene_change_pct, scene_change_detected = (
            self._scene_change(frame)
        )

        current_joints = self._landmark_map(pose_result)

        pose_visible = (
            bool(pose_result.get("pose_detected"))
            and len(current_joints) >= 4
        )

        score = None
        moving = None

        common = [
            index
            for index in current_joints
            if index in self._previous_joints
        ]

        if pose_visible and len(common) >= 4:
            scale = self._normalizing_scale(
                current_joints
            )

            if scale > 0:
                displacements = [
                    min(
                        1.0,
                        hypot(
                            current_joints[index][0]
                            - self._previous_joints[index][0],
                            current_joints[index][1]
                            - self._previous_joints[index][1],
                        ) / scale,
                    )
                    for index in common
                ]

                largest = sorted(
                    displacements,
                    reverse=True,
                )[:3]

                if largest:
                    score = sum(largest) / len(largest)

                    self._movement_history.append(
                        score >= self.joint_motion_threshold
                    )

                    moving = (
                        sum(self._movement_history) >= 2
                        or score
                        >= self.joint_motion_threshold * 2.0
                    )

        if pose_visible:
            if moving is None:
                status = "TRACKING BODY LANDMARKS"
            elif moving:
                status = "BODY LANDMARK MOVEMENT"
            else:
                status = "LOW BODY LANDMARK MOVEMENT"

        elif scene_change_detected:
            status = (
                "SCENE CHANGE — "
                "BODY MOVEMENT UNASSESSED"
            )

        else:
            status = (
                "BODY POSE NOT VISIBLE — "
                "MOVEMENT UNASSESSED"
            )

        # Reset joint history when pose detection is lost,
        # preventing false movement from a sudden reacquisition.
        self._previous_joints = (
            current_joints if pose_visible else {}
        )

        return {
            "pose_landmarks_visible": pose_visible,
            "tracked_joints": len(current_joints),
            "body_motion_score": (
                round(score, 5)
                if score is not None
                else None
            ),
            "body_motion_detected": moving,
            "scene_change_pct": (
                round(scene_change_pct, 4)
                if scene_change_pct is not None
                else None
            ),
            "scene_change_detected": bool(
                scene_change_detected
            ),
            "status": status,
            "disclaimer": (
                "Experimental visual indicator; "
                "not a medical assessment."
            ),
        }