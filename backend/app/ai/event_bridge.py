from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.ai.behavior_analyzer import BehaviorResult
from app.services.alert import create_alert
from app.services.event import create_event


class AIEventBridge:
    """
    Connects EMPATH AI behavior analysis to the Event and Alert layers.

    Current actionable AI event:
        POSSIBLE_FALL

    Pipeline:

        BehaviorAnalyzer
              ↓
            Event
              ↓
            Alert

    The bridge uses edge detection and a cooldown so that one
    sustained AI event does not create a database record for every
    video frame.

    A new fall episode detected during cooldown is held pending
    while the possible-fall signal remains active. This allows the
    episode to be processed after cooldown instead of immediately
    discarding it.

    This is an operational safety workflow and not a medical
    diagnostic system.
    """

    def __init__(
        self,
        cooldown_seconds: float = 10.0,
    ) -> None:
        # NEW: Prevent an invalid cooldown configuration.
        if cooldown_seconds < 0:
            raise ValueError(
                "cooldown_seconds must be >= 0"
            )

        self.cooldown_seconds = float(
            cooldown_seconds
        )

        self._possible_fall_active = False
        self._last_event_time = 0.0

        # NEW: Retain a new fall episode while cooldown is active.
        self._pending_fall: dict[str, Any] | None = None

    def process(
        self,
        db: Session,
        behavior: BehaviorResult,
        *,
        camera_id: int | None = None,
        patient_id: int | None = None,
        extra_metadata: dict[str, Any] | None = None,
    ):
        """
        Process one BehaviorAnalyzer result.

        Returns:
            dict containing the created Event and Alert, or None.
        """

        current_possible_fall = bool(
            behavior.possible_fall
        )

        now = time.monotonic()

        new_possible_fall = (
            current_possible_fall
            and not self._possible_fall_active
        )

        cooldown_finished = (
            now - self._last_event_time
            >= self.cooldown_seconds
        )

        result = None

        # --------------------------------------------------------
        # NEW: Preserve a new fall episode during cooldown
        # --------------------------------------------------------

        if new_possible_fall:
            self._pending_fall = {
                "behavior": behavior,
                "camera_id": camera_id,
                "patient_id": patient_id,
                "extra_metadata": dict(
                    extra_metadata or {}
                ),
            }

        # Do not create a delayed alert for a fall signal that
        # ended before its pending event could be processed.
        if not current_possible_fall:
            self._pending_fall = None

        pending = self._pending_fall

        # --------------------------------------------------------
        # AI → EVENT → ALERT
        # --------------------------------------------------------

        # IMPROVED: Process either an immediate fall or a pending
        # fall whose cooldown has now finished.
        if (
            current_possible_fall
            and pending is not None
            and cooldown_finished
        ):
            pending_behavior = pending["behavior"]

            metadata: dict[str, Any] = {
                "ai_state": pending_behavior.posture,
                "movement_score": (
                    pending_behavior.movement_score
                ),
                "body_angle": pending_behavior.body_angle,
                "ai_confidence": (
                    pending_behavior.confidence
                ),
                "reason": pending_behavior.reason,
            }

            if pending["extra_metadata"]:
                metadata.update(
                    pending["extra_metadata"]
                )

            # ----------------------------------------------------
            # 1. Create Event
            # ----------------------------------------------------

            event = create_event(
                db,
                event_type="possible_fall",
                source_type="ai_visual",
                severity="high",
                camera_id=pending["camera_id"],
                patient_id=pending["patient_id"],
                confidence=pending_behavior.confidence,
                description=(
                    "Possible visual fall event detected. "
                    "Staff verification required. "
                    f"{pending_behavior.reason}"
                ),
                metadata=metadata,
            )

            # ----------------------------------------------------
            # 2. Create Alert linked to Event
            # ----------------------------------------------------

            alert = create_alert(
                db,
                event=event,
                priority="high",
                title="Possible Fall Detected",
                message=(
                    "EMPATH detected a possible visual fall "
                    "event. Staff verification is required."
                ),
            )

            self._last_event_time = time.monotonic()

            # NEW: Clear pending state only after both calls return.
            self._pending_fall = None

            result = {
                "event": event,
                "alert": alert,
            }

        # --------------------------------------------------------
        # Remember current AI state.
        #
        # This prevents one persistent fall from generating
        # another Event + Alert every frame.
        # --------------------------------------------------------

        self._possible_fall_active = (
            current_possible_fall
        )

        return result

    def reset(self) -> None:
        """
        Reset bridge state.

        Call this when:
          - a live monitoring session ends
          - a video analysis ends
          - a new patient/session begins
        """

        self._possible_fall_active = False
        self._last_event_time = 0.0

        # NEW: Do not carry pending state into another session.
        self._pending_fall = None