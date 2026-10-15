from __future__ import annotations

from app.ai.behavior_analyzer import BehaviorResult
from app.ai.event_bridge import AIEventBridge
from app.core.database import SessionLocal


def main() -> None:
    print("==============================================")
    print("EMPATH AI → EVENT → ALERT TEST")
    print("==============================================")

    db = SessionLocal()

    bridge = AIEventBridge(
        cooldown_seconds=60.0
    )

    # --------------------------------------------------------
    # Simulated AI result
    # --------------------------------------------------------

    behavior = BehaviorResult(
        pose_detected=True,
        posture="POSSIBLE_FALL",
        movement_score=0.42,
        body_angle=68.5,
        possible_fall=True,
        confidence=0.84,
        reason=(
            "Temporal fall candidate confirmed using "
            "recent body movement and body-position change."
        ),
    )

    print()
    print("Simulated AI state:")
    print(
        f"Posture:     {behavior.posture}"
    )
    print(
        f"Confidence:  {behavior.confidence:.2f}"
    )
    print(
        f"Movement:    {behavior.movement_score:.3f}"
    )
    print(
        f"Body angle:  {behavior.body_angle:.1f}°"
    )

    # --------------------------------------------------------
    # AI → EVENT → ALERT
    # --------------------------------------------------------

    result = bridge.process(
        db,
        behavior,
        camera_id=1,
        patient_id=1,
        extra_metadata={
            "test_mode": True,
            "test_source": "test_event_bridge",
        },
    )

    print()

    if result is None:
        print(
            "ERROR: Event and alert were not created."
        )
        db.close()
        return

    event = result["event"]
    alert = result["alert"]

    print("==============================================")
    print("EVENT CREATED")
    print("==============================================")
    print(
        f"Event ID:       {event.id}"
    )
    print(
        f"Event type:     {event.event_type}"
    )
    print(
        f"Source type:    {event.source_type}"
    )
    print(
        f"Severity:       {event.severity}"
    )
    print(
        f"Status:         {event.status}"
    )
    print(
        f"Confidence:     {event.confidence}"
    )
    print(
        f"Camera ID:      {event.camera_id}"
    )
    print(
        f"Patient ID:     {event.patient_id}"
    )

    print()
    print("==============================================")
    print("ALERT CREATED")
    print("==============================================")
    print(
        f"Alert ID:       {alert.id}"
    )
    print(
        f"Event ID:       {alert.event_id}"
    )
    print(
        f"Priority:       {alert.priority}"
    )
    print(
        f"Status:         {alert.status}"
    )
    print(
        f"Title:          {alert.title}"
    )
    print(
        f"Message:        {alert.message}"
    )

    # --------------------------------------------------------
    # Duplicate protection
    # --------------------------------------------------------

    second_result = bridge.process(
        db,
        behavior,
        camera_id=1,
        patient_id=1,
    )

    print()

    if second_result is None:
        print(
            "Duplicate event/alert protection: OK"
        )
    else:
        print(
            "WARNING: Duplicate Event/Alert was created."
        )

    db.close()

    print()
    print("==============================================")
    print("AI → EVENT → ALERT TEST COMPLETE")
    print("==============================================")


if __name__ == "__main__":
    main()