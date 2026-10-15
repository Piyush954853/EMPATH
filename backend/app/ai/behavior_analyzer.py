from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from math import acos, atan2, degrees, hypot
from typing import Any

# MediaPipe Pose landmark indices.
LEFT_SHOULDER = 11
RIGHT_SHOULDER = 12
LEFT_HIP = 23
RIGHT_HIP = 24
LEFT_KNEE = 25
RIGHT_KNEE = 26
LEFT_ANKLE = 27
RIGHT_ANKLE = 28

@dataclass
class BehaviorResult:
    pose_detected: bool
    posture: str
    movement_score: float
    body_angle: float
    possible_fall: bool
    confidence: float
    reason: str

class BehaviorAnalyzer:
    """
    Temporal visual-safety analyzer for EMPATH.
    Designed to work with both:
      - front-facing cameras
      - side-view cameras
    Main signals:
      - torso angle
      - knee flexion
      - body height/compression
      - hip/body-center movement
      - temporal transitions
      - short pose-loss tolerance
    This is a heuristic safety-event detector,
    not a medical diagnostic model.
    """

    def __init__(
        self,
        history_size: int = 30,
        fall_angle_threshold: float = 55.0,
        movement_threshold: float = 0.10,
        fall_persistence_frames: int = 4,
        sitting_knee_angle: float = 150.0,
        sitting_compression_ratio: float = 0.78,
        getting_up_vertical_motion: float = 0.004,
        getting_up_knee_change: float = 2.0,
        pose_loss_grace_frames: int = 15,
        # Additional thresholds for a sudden collapse from a seated posture.
        sitting_fall_vertical_motion: float = 0.015,
        sitting_fall_body_angle: float = 30.0,
        sitting_fall_compression_ratio: float = 0.88,
        # Rapid-transition thresholds help catch short falls between sampled poses.
        rapid_transition_movement_threshold: float = 0.025,
        rapid_transition_angle_delta: float = 15.0,
    ) -> None:
        self.history = deque(maxlen=history_size)
        self.fall_angle_threshold = fall_angle_threshold
        self.movement_threshold = movement_threshold
        self.fall_persistence_frames = fall_persistence_frames
        self.sitting_knee_angle = sitting_knee_angle
        self.sitting_compression_ratio = sitting_compression_ratio
        self.getting_up_vertical_motion = getting_up_vertical_motion
        self.getting_up_knee_change = getting_up_knee_change
        self.pose_loss_grace_frames = pose_loss_grace_frames
        # Additional configuration for seated-to-collapse detection.
        self.sitting_fall_vertical_motion = sitting_fall_vertical_motion
        self.sitting_fall_body_angle = sitting_fall_body_angle
        self.sitting_fall_compression_ratio = sitting_fall_compression_ratio
        self.rapid_transition_movement_threshold = (
            rapid_transition_movement_threshold
        )
        self.rapid_transition_angle_delta = rapid_transition_angle_delta
        self._fall_candidate_frames = 0
        self._missing_pose_frames = 0
        # Keeps a seated-collapse candidate active across a short transition
        # from leaning to horizontal posture while persistence is evaluated.
        self._seated_collapse_active = False
        self.previous_posture = "NO_PERSON"
        # Standing reference.
        # This adapts to the person's distance from the camera.
        self._standing_body_height: float | None = None

    # ============================================================
    # BASIC GEOMETRY
    # ============================================================

    @staticmethod
    def _point(
        landmarks: list[dict[str, Any]],
        index: int,
    ) -> tuple[float, float]:
        landmark = landmarks[index]
        return (
            float(landmark["x"]),
            float(landmark["y"]),
        )

    @staticmethod
    def _midpoint(
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> tuple[float, float]:
        return (
            (first[0] + second[0]) / 2.0,
            (first[1] + second[1]) / 2.0,
        )

    @staticmethod
    def _distance(
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> float:
        return hypot(
            first[0] - second[0],
            first[1] - second[1],
        )

    @staticmethod
    def _body_angle(
        shoulder_center: tuple[float, float],
        hip_center: tuple[float, float],
    ) -> float:
        """
        Torso angle relative to vertical.
        0°   = approximately upright
        90°  = approximately horizontal
        """
        dx = hip_center[0] - shoulder_center[0]
        dy = hip_center[1] - shoulder_center[1]
        return float(
            degrees(
                atan2(
                    abs(dx),
                    abs(dy),
                )
            )
        )

    @staticmethod
    def _joint_angle(
        first: tuple[float, float],
        joint: tuple[float, float],
        third: tuple[float, float],
    ) -> float:
        """
        Calculate angle at the joint.
        180° = approximately straight
        Lower values = more flexed
        """
        vector_a = (
            first[0] - joint[0],
            first[1] - joint[1],
        )
        vector_b = (
            third[0] - joint[0],
            third[1] - joint[1],
        )
        magnitude_a = hypot(
            vector_a[0],
            vector_a[1],
        )
        magnitude_b = hypot(
            vector_b[0],
            vector_b[1],
        )
        if magnitude_a == 0.0 or magnitude_b == 0.0:
            return 180.0
        cosine_value = (
            vector_a[0] * vector_b[0]
            + vector_a[1] * vector_b[1]
        ) / (
            magnitude_a * magnitude_b
        )
        cosine_value = max(
            -1.0,
            min(1.0, cosine_value),
        )
        return float(
            degrees(
                acos(cosine_value)
            )
        )

    # ============================================================
    # FEATURE EXTRACTION
    # ============================================================

    def _extract_features(
        self,
        landmarks: list[dict[str, Any]],
    ) -> dict[str, float]:
        left_shoulder = self._point(
            landmarks,
            LEFT_SHOULDER,
        )
        right_shoulder = self._point(
            landmarks,
            RIGHT_SHOULDER,
        )
        left_hip = self._point(
            landmarks,
            LEFT_HIP,
        )
        right_hip = self._point(
            landmarks,
            RIGHT_HIP,
        )
        left_knee = self._point(
            landmarks,
            LEFT_KNEE,
        )
        right_knee = self._point(
            landmarks,
            RIGHT_KNEE,
        )
        left_ankle = self._point(
            landmarks,
            LEFT_ANKLE,
        )
        right_ankle = self._point(
            landmarks,
            RIGHT_ANKLE,
        )
        shoulder_center = self._midpoint(
            left_shoulder,
            right_shoulder,
        )
        hip_center = self._midpoint(
            left_hip,
            right_hip,
        )
        knee_center = self._midpoint(
            left_knee,
            right_knee,
        )
        ankle_center = self._midpoint(
            left_ankle,
            right_ankle,
        )
        body_center = self._midpoint(
            shoulder_center,
            hip_center,
        )
        body_angle = self._body_angle(
            shoulder_center,
            hip_center,
        )
        left_knee_angle = self._joint_angle(
            left_hip,
            left_knee,
            left_ankle,
        )
        right_knee_angle = self._joint_angle(
            right_hip,
            right_knee,
            right_ankle,
        )
        knee_angle = (
            left_knee_angle
            + right_knee_angle
        ) / 2.0
        # Vertical body span.
        body_height = self._distance(
            shoulder_center,
            ankle_center,
        )
        # Useful for front-view sitting detection.
        torso_height = self._distance(
            shoulder_center,
            hip_center,
        )
        leg_height = self._distance(
            hip_center,
            knee_center,
        ) + self._distance(
            knee_center,
            ankle_center,
        )
        return {
            "center_x": body_center[0],
            "center_y": body_center[1],
            "shoulder_y": shoulder_center[1],
            "hip_y": hip_center[1],
            "knee_y": knee_center[1],
            "ankle_y": ankle_center[1],
            "body_angle": body_angle,
            "knee_angle": knee_angle,
            "body_height": body_height,
            "torso_height": torso_height,
            "leg_height": leg_height,
        }

    # ============================================================
    # TEMPORAL FEATURES
    # ============================================================

    def _movement_score(
        self,
        current_center: tuple[float, float],
    ) -> float:
        if not self.history:
            return 0.0
        previous = self.history[-1]
        movement = self._distance(
            current_center,
            (
                previous["center_x"],
                previous["center_y"],
            ),
        )
        return float(
            min(movement, 1.0)
        )

    def _vertical_motion(
        self,
        current_center_y: float,
    ) -> float:
        """
        Positive = moving downward in image.
        Negative = moving upward in image.
        """
        if not self.history:
            return 0.0
        previous_y = self.history[-1]["center_y"]
        return float(
            current_center_y - previous_y
        )

    def _knee_change(
        self,
        current_knee_angle: float,
    ) -> float:
        if not self.history:
            return 0.0
        previous_knee_angle = self.history[-1][
            "knee_angle"
        ]
        return float(
            current_knee_angle
            - previous_knee_angle
        )

    # ============================================================
    # STANDING BASELINE
    # ============================================================

    def _update_standing_baseline(
        self,
        features: dict[str, float],
    ) -> None:
        """
        Learn the person's approximate standing height.
        We only update this while the person appears upright
        and relatively stable.
        """
        if features["body_angle"] >= 25.0:
            return
        if self.history:
            previous = self.history[-1]
            previous_center = (
                previous["center_x"],
                previous["center_y"],
            )
            current_center = (
                features["center_x"],
                features["center_y"],
            )
            movement = self._distance(
                current_center,
                previous_center,
            )
            if movement > 0.05:
                return
        current_height = features["body_height"]
        if current_height <= 0.05:
            return
        if self._standing_body_height is None:
            self._standing_body_height = current_height
            return
        # Exponential moving average.
        self._standing_body_height = (
            0.95 * self._standing_body_height
            + 0.05 * current_height
        )

    # ============================================================
    # POSTURE CLASSIFICATION
    # ============================================================

    def _compression_ratio(
        self,
        body_height: float,
    ) -> float:
        if (
            self._standing_body_height is None
            or self._standing_body_height <= 0.0
        ):
            return 1.0
        return float(
            body_height
            / self._standing_body_height
        )

    def _classify_posture(
        self,
        features: dict[str, float],
        vertical_motion: float,
        knee_change: float,
    ) -> str:
        body_angle = features["body_angle"]
        knee_angle = features["knee_angle"]
        compression = self._compression_ratio(
            features["body_height"]
        )
        # --------------------------------------------------------
        # SIDE VIEW / HORIZONTAL BODY
        # --------------------------------------------------------
        if body_angle >= self.fall_angle_threshold:
            return "HORIZONTAL"
        # --------------------------------------------------------
        # GETTING UP
        # --------------------------------------------------------
        if (
            self.previous_posture == "SITTING"
            and vertical_motion
            <= -self.getting_up_vertical_motion
            and knee_change
            >= self.getting_up_knee_change
        ):
            return "GETTING_UP"
        # --------------------------------------------------------
        # FRONT VIEW SITTING
        # --------------------------------------------------------
        front_sitting_signal = (
            knee_angle
            < self.sitting_knee_angle
            and compression
            < self.sitting_compression_ratio
        )
        # Also allow a strongly flexed knee signal when the
        # standing baseline has not yet stabilized.
        knee_only_sitting_signal = (
            knee_angle < 125.0
            and body_angle < 40.0
        )
        if (
            front_sitting_signal
            or knee_only_sitting_signal
        ):
            return "SITTING"
        # --------------------------------------------------------
        # LEANING
        # --------------------------------------------------------
        if body_angle >= 25.0:
            return "LEANING"
        # --------------------------------------------------------
        # NORMAL STANDING
        # --------------------------------------------------------
        return "UPRIGHT"

    # ============================================================
    # FALL DETECTION
    # ============================================================

    def _sitting_collapse_signal(
        self,
        features: dict[str, float],
        movement_score: float,
        vertical_motion: float,
    ) -> bool:
        """
        Detect a sudden downward collapse that begins from sitting.
        This supplements the original horizontal and front-view fall
        signals. It is intentionally restricted to a seated transition
        and combines movement with torso tipping or sudden body-span loss
        to avoid treating ordinary sitting as a fall by itself.
        """
        if self.previous_posture != "SITTING" or not self.history:
            return False
        previous = self.history[-1]
        # Use hip displacement as an additional downward-motion cue.
        hip_vertical_motion = (
            features["hip_y"] - previous["hip_y"]
        )
        downward_motion = max(
            vertical_motion,
            hip_vertical_motion,
        )
        sudden_downward_motion = (
            downward_motion >= self.sitting_fall_vertical_motion
        )
        # A fall can move the body centre less than the original general
        # movement threshold when the camera is far from the person.
        significant_movement = (
            movement_score >= max(
                0.025,
                self.movement_threshold * 0.35,
            )
        )
        torso_tipping = (
            features["body_angle"] >= self.sitting_fall_body_angle
        )
        previous_body_height = previous.get("body_height", 0.0)
        sudden_body_compression = (
            previous_body_height > 0.0
            and features["body_height"]
            <= previous_body_height * self.sitting_fall_compression_ratio
        )
        return (
            sudden_downward_motion
            and significant_movement
            and (torso_tipping or sudden_body_compression)
        )

    def _front_view_fall_signal(
        self,
        features: dict[str, float],
        movement_score: float,
        vertical_motion: float,
    ) -> bool:
        """
        Front-view fall/collapse signal.
        A front camera cannot reliably use torso rotation alone,
        so we look for a rapid downward body movement combined
        with a sudden reduction in vertical body span.
        """
        compression = self._compression_ratio(
            features["body_height"]
        )
        sudden_downward_motion = (
            vertical_motion >= 0.025
        )
        significant_movement = (
            movement_score
            >= self.movement_threshold
        )
        compressed_body = (
            compression < 0.68
        )
        return (
            sudden_downward_motion
            and significant_movement
            and compressed_body
        )

    # ============================================================
    # MAIN ANALYSIS
    # ============================================================

    def analyze(
        self,
        pose_result: dict[str, Any],
    ) -> BehaviorResult:
        """
        Analyze one pose-inference result.
        """
        pose_detected = bool(
            pose_result.get("pose_detected")
        )
        poses = pose_result.get(
            "poses",
            [],
        )
        # --------------------------------------------------------
        # TEMPORARY POSE LOSS
        # --------------------------------------------------------
        if not pose_detected or not poses:
            self._missing_pose_frames += 1
            self._fall_candidate_frames = 0
            # A collapse candidate cannot be continued without pose data.
            self._seated_collapse_active = False
            # Do not immediately erase the last known state.
            if (
                self.previous_posture
                not in {"NO_PERSON", "INSUFFICIENT_DATA"}
                and self._missing_pose_frames
                <= self.pose_loss_grace_frames
            ):
                return BehaviorResult(
                    pose_detected=False,
                    posture=self.previous_posture,
                    movement_score=0.0,
                    body_angle=0.0,
                    possible_fall=False,
                    confidence=0.0,
                    reason=(
                        "Pose temporarily unavailable; "
                        "retaining previous behavioral state."
                    ),
                )
            self.previous_posture = "NO_PERSON"
            return BehaviorResult(
                pose_detected=False,
                posture="NO_PERSON",
                movement_score=0.0,
                body_angle=0.0,
                possible_fall=False,
                confidence=0.0,
                reason="No pose detected.",
            )
        # Pose successfully detected.
        self._missing_pose_frames = 0
        landmarks = poses[0].get(
            "landmarks",
            [],
        )
        if len(landmarks) < 29:
            return BehaviorResult(
                pose_detected=False,
                posture="INSUFFICIENT_DATA",
                movement_score=0.0,
                body_angle=0.0,
                possible_fall=False,
                confidence=0.0,
                reason="Insufficient pose landmarks.",
            )
        # --------------------------------------------------------
        # FEATURES
        # --------------------------------------------------------
        features = self._extract_features(
            landmarks
        )
        current_center = (
            features["center_x"],
            features["center_y"],
        )
        movement_score = self._movement_score(
            current_center
        )
        vertical_motion = self._vertical_motion(
            features["center_y"]
        )
        knee_change = self._knee_change(
            features["knee_angle"]
        )
        # Learn standing reference before classification.
        if (
            self.previous_posture
            in {"UPRIGHT", "NO_PERSON"}
        ):
            self._update_standing_baseline(
                features
            )
        # --------------------------------------------------------
        # POSTURE
        # --------------------------------------------------------
        posture = self._classify_posture(
            features,
            vertical_motion,
            knee_change,
        )
        # --------------------------------------------------------
        # FALL CANDIDATE
        # --------------------------------------------------------
        horizontal_signal = (
            posture == "HORIZONTAL"
            and movement_score
            >= self.movement_threshold
        )
        front_fall_signal = (
            self._front_view_fall_signal(
                features,
                movement_score,
                vertical_motion,
            )
        )
        # NEW: Catch a sudden collapse that starts from sitting even when
        # a standing-height baseline was never established by the video.
        seated_collapse_signal = self._sitting_collapse_signal(
            features,
            movement_score,
            vertical_motion,
        )
        # Keep the new candidate alive through a brief LEANING/HORIZONTAL
        # transition so that persistence can be evaluated across frames.
        seated_collapse_continuation = (
            self._seated_collapse_active
            and self._fall_candidate_frames > 0
            and posture in {"LEANING", "HORIZONTAL"}
        )
        seated_collapse_candidate = (
            seated_collapse_signal
            or seated_collapse_continuation
        )

        # NEW: Catch a rapid transition from an active posture into a
        # horizontal posture even when the centre-of-body movement alone
        # does not cross the original, stricter movement threshold.
        previous_body_angle = (
            float(self.history[-1].get("body_angle", features["body_angle"]))
            if self.history
            else float(features["body_angle"])
        )
        body_angle_delta = (
            float(features["body_angle"]) - previous_body_angle
        )
        rapid_horizontal_transition = (
            posture == "HORIZONTAL"
            and self.previous_posture
            in {
                "UPRIGHT",
                "LEANING",
                "SITTING",
                "GETTING_UP",
            }
            and (
                movement_score >= self.rapid_transition_movement_threshold
                or vertical_motion >= self.sitting_fall_vertical_motion * 0.75
                or (
                    self.previous_posture == "SITTING"
                    and body_angle_delta >= self.rapid_transition_angle_delta
                )
            )
        )

        previous_active_posture = (
            self.previous_posture
            in {
                "UPRIGHT",
                "LEANING",
                "SITTING",
                "GETTING_UP",
                # Keep a confirmed episode active while the body remains in transition.
                "POSSIBLE_FALL",
            }
            # A horizontal posture may continue a fall candidate, but only
            # after a candidate was already triggered from an active posture.
            # This lets the configured persistence threshold work across
            # consecutive moving horizontal frames without treating every
            # already-horizontal pose as a new fall transition.
            or (
                self.previous_posture == "HORIZONTAL"
                and self._fall_candidate_frames > 0
            )
        )
        possible_fall_frame = (
            previous_active_posture
            and (
                horizontal_signal
                or front_fall_signal
                or seated_collapse_candidate
            )
        )
        if possible_fall_frame:
            self._fall_candidate_frames += 1
        else:
            self._fall_candidate_frames = max(
                0,
                self._fall_candidate_frames - 1,
            )
        possible_fall = (
            self._fall_candidate_frames
            >= self.fall_persistence_frames
            or rapid_horizontal_transition
        )
        # NEW: Maintain the seated-collapse latch only while the same
        # transition is being evaluated; clear it after recovery/reset.
        if seated_collapse_signal:
            self._seated_collapse_active = True
        elif (
            self._fall_candidate_frames == 0
            or posture in {"UPRIGHT", "SITTING", "GETTING_UP"}
        ):
            self._seated_collapse_active = False
        # --------------------------------------------------------
        # CONFIDENCE + EXPLANATION
        # --------------------------------------------------------
        if possible_fall:
            posture = "POSSIBLE_FALL"
            confidence = min(
                0.95,
                0.55
                + min(
                    movement_score * 1.5,
                    0.20,
                )
                + min(
                    max(
                        (
                            features["body_angle"]
                            - self.fall_angle_threshold
                        )
                        / 100.0,
                        0.0,
                    ),
                    0.10,
                )
                + min(
                    max(
                        vertical_motion * 2.0,
                        0.0,
                    ),
                    0.10,
                ),
            )
            if seated_collapse_candidate:
                reason = (
                    "Temporal seated-collapse candidate detected using "
                    "downward body movement and a torso/body-position change. "
                    "Urgent staff verification is required; this is not a "
                    "confirmed fall."
                )
            elif rapid_horizontal_transition:
                reason = (
                    "Rapid transition to horizontal body orientation detected. "
                    "Urgent staff verification is required; this is not a "
                    "confirmed fall."
                )
            else:
                reason = (
                    "Temporal fall candidate confirmed using "
                    "recent body movement and body-position change. "
                    "Staff verification is required."
                )
        elif features["body_angle"] >= self.fall_angle_threshold:
            confidence = 0.35
            reason = (
                "Horizontal body orientation detected; "
                "waiting for temporal confirmation."
            )
        elif posture == "GETTING_UP":
            confidence = 0.60
            reason = (
                "Upward body movement with increasing "
                "knee extension suggests transition "
                "from sitting toward standing."
            )
        elif posture == "SITTING":
            compression = self._compression_ratio(
                features["body_height"]
            )
            confidence = 0.55
            reason = (
                "Front/side-view seated posture indicated "
                "by knee flexion and reduced body height. "
                f"Compression={compression:.2f}."
            )
        elif posture == "LEANING":
            confidence = 0.25
            reason = (
                "Torso orientation indicates leaning; "
                "no fall event confirmed."
            )
        else:
            confidence = 0.05
            reason = "Stable upright posture."
        # --------------------------------------------------------
        # SAVE HISTORY
        # --------------------------------------------------------
        self.history.append(
            features
        )
        self.previous_posture = posture
        return BehaviorResult(
            pose_detected=True,
            posture=posture,
            movement_score=movement_score,
            body_angle=features["body_angle"],
            possible_fall=possible_fall,
            confidence=float(confidence),
            reason=reason,
        )

    # ============================================================
    # RESET
    # ============================================================

    def reset(self) -> None:
        self.history.clear()
        self._fall_candidate_frames = 0
        self._missing_pose_frames = 0
        self.previous_posture = "NO_PERSON"
        self._standing_body_height = None
        # Reset both collapse/transition-related temporal states.
        self._seated_collapse_active = False
