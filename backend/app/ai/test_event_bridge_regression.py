"""Automated, database-free regression tests for EMPATH's AI event bridge.

These tests mock the persistence services so they never create real database
Event or Alert records. Keep the existing test_event_bridge.py demo script;
this file adds pytest coverage alongside it.
"""
from types import SimpleNamespace

import app.ai.event_bridge as event_bridge_module
from app.ai.behavior_analyzer import BehaviorResult
from app.ai.event_bridge import AIEventBridge


class FakeClock:
    def __init__(self, initial: float = 100.0) -> None:
        self.now = initial

    def monotonic(self) -> float:
        return self.now


def make_behavior(possible_fall: bool) -> BehaviorResult:
    return BehaviorResult(
        pose_detected=True,
        posture="POSSIBLE_FALL" if possible_fall else "UPRIGHT",
        movement_score=0.42 if possible_fall else 0.01,
        body_angle=68.5 if possible_fall else 4.0,
        possible_fall=possible_fall,
        confidence=0.84 if possible_fall else 0.05,
        reason=(
            "Synthetic regression-test fall signal."
            if possible_fall
            else "Synthetic regression-test stable posture."
        ),
    )


def install_persistence_mocks(monkeypatch):
    created_events = []
    created_alerts = []

    def fake_create_event(db, **kwargs):
        event = SimpleNamespace(
            id=21 + len(created_events),
            event_type=kwargs["event_type"],
            source_type=kwargs["source_type"],
            severity=kwargs["severity"],
            camera_id=kwargs["camera_id"],
            patient_id=kwargs["patient_id"],
            confidence=kwargs["confidence"],
            description=kwargs["description"],
            metadata=kwargs["metadata"],
        )
        created_events.append(event)
        return event

    def fake_create_alert(db, *, event, priority, title, message=None):
        alert = SimpleNamespace(
            id=9 + len(created_alerts),
            event_id=event.id,
            priority=priority,
            title=title,
            message=message,
            status="active",
        )
        created_alerts.append(alert)
        return alert

    monkeypatch.setattr(event_bridge_module, "create_event", fake_create_event)
    monkeypatch.setattr(event_bridge_module, "create_alert", fake_create_alert)
    return created_events, created_alerts


def test_non_fall_does_not_create_event_or_alert(monkeypatch):
    created_events, created_alerts = install_persistence_mocks(monkeypatch)
    bridge = AIEventBridge(cooldown_seconds=10.0)

    result = bridge.process(object(), make_behavior(False), camera_id=1, patient_id=1)

    assert result is None
    assert created_events == []
    assert created_alerts == []


def test_new_possible_fall_creates_linked_event_and_alert(monkeypatch):
    created_events, created_alerts = install_persistence_mocks(monkeypatch)
    clock = FakeClock(100.0)
    monkeypatch.setattr(event_bridge_module.time, "monotonic", clock.monotonic)
    bridge = AIEventBridge(cooldown_seconds=10.0)

    result = bridge.process(
        object(),
        make_behavior(True),
        camera_id=1,
        patient_id=1,
        extra_metadata={"test_mode": True},
    )

    assert result is not None
    assert len(created_events) == 1
    assert len(created_alerts) == 1
    assert result["event"] is created_events[0]
    assert result["alert"] is created_alerts[0]
    assert created_events[0].event_type == "possible_fall"
    assert created_events[0].source_type == "ai_visual"
    assert created_events[0].severity == "high"
    assert created_events[0].metadata["test_mode"] is True
    assert created_alerts[0].event_id == created_events[0].id
    assert created_alerts[0].priority == "high"


def test_sustained_possible_fall_does_not_create_duplicate(monkeypatch):
    created_events, created_alerts = install_persistence_mocks(monkeypatch)
    clock = FakeClock(100.0)
    monkeypatch.setattr(event_bridge_module.time, "monotonic", clock.monotonic)
    bridge = AIEventBridge(cooldown_seconds=10.0)
    behavior = make_behavior(True)

    first_result = bridge.process(object(), behavior, camera_id=1, patient_id=1)
    clock.now = 101.0
    second_result = bridge.process(object(), behavior, camera_id=1, patient_id=1)

    assert first_result is not None
    assert second_result is None
    assert len(created_events) == 1
    assert len(created_alerts) == 1


def test_cooldown_blocks_retrigger_until_cooldown_expires(monkeypatch):
    created_events, created_alerts = install_persistence_mocks(monkeypatch)
    clock = FakeClock(100.0)
    monkeypatch.setattr(event_bridge_module.time, "monotonic", clock.monotonic)
    bridge = AIEventBridge(cooldown_seconds=10.0)

    first_result = bridge.process(object(), make_behavior(True), camera_id=1, patient_id=1)
    assert first_result is not None

    clock.now = 101.0
    assert bridge.process(object(), make_behavior(False), camera_id=1, patient_id=1) is None

    clock.now = 105.0
    blocked_result = bridge.process(object(), make_behavior(True), camera_id=1, patient_id=1)
    assert blocked_result is None
    assert len(created_events) == 1

    # The signal must clear again before a new edge can be emitted.
    clock.now = 106.0
    assert bridge.process(object(), make_behavior(False), camera_id=1, patient_id=1) is None

    clock.now = 111.0
    retriggered_result = bridge.process(object(), make_behavior(True), camera_id=1, patient_id=1)

    assert retriggered_result is not None
    assert len(created_events) == 2
    assert len(created_alerts) == 2
    assert created_alerts[1].event_id == created_events[1].id
