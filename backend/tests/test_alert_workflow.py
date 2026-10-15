
import json
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Import models so their foreign-key targets are registered.
import app.models  # noqa: F401

from app.models.alert import Alert
from app.models.alert_handoff import AlertHandoffHistory
from app.services import alert as alert_service
from app.services.alert import (
    acknowledge_alert,
    get_alert_handoff_history,
    resolve_alert,
    transfer_alert,
)
from app.services.alert_summary import generate_alert_summary


@pytest.fixture
def db_session():
    """Create an isolated, in-memory SQLite database for each test."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Alert.__table__.create(bind=engine)
    AlertHandoffHistory.__table__.create(bind=engine)

    TestSession = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )
    db = TestSession()

    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def make_test_alert(
    db_session,
    *,
    status="active",
    assigned_to_user_id=None,
):
    """Create an alert inside the isolated test database."""

    alert = Alert(
        event_id=101,
        priority="medium",
        status=status,
        title="TEST - Automated Alert",
        message="Test-only alert message.",
        summary="Test-only summary.",
        assigned_to_user_id=assigned_to_user_id,
    )

    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    return alert


def test_test_record_uses_fixed_summary():
    """Test records should not invoke the language model."""

    event = SimpleNamespace(
        id=15,
        event_type="alert_handoff_test",
        source_type="manual_test",
        severity="medium",
        camera_id=1,
        patient_id=None,
        confidence=None,
        description="Test-only event.",
        detected_at=None,
        metadata_json=json.dumps({"test_only": True}),
    )

    summary = generate_alert_summary(
        event,
        title="TEST - Summary",
        message="Test-only message.",
        priority="medium",
    )

    assert "Software test record" in summary
    assert "not a real clinical incident" in summary
    assert "Camera ID" in summary


def test_create_alert_saves_generated_summary(
    db_session,
    monkeypatch,
):
    """Alert creation should persist the generated summary."""

    monkeypatch.setattr(
        alert_service,
        "generate_alert_summary",
        lambda event, **kwargs: "Generated test summary.",
    )

    event = SimpleNamespace(id=102)

    alert = alert_service.create_alert(
        db_session,
        event=event,
        priority="medium",
        title="TEST - Summary Persistence",
        message="Testing summary persistence.",
    )

    saved_alert = db_session.get(Alert, alert.id)

    assert saved_alert is not None
    assert saved_alert.status == "active"
    assert saved_alert.summary == "Generated test summary."


def test_transfer_updates_assignee_and_history(db_session):
    """A transfer should update assignment and save an audit record."""

    alert = make_test_alert(
        db_session,
        assigned_to_user_id=7,
    )

    updated_alert, history = transfer_alert(
        db_session,
        alert=alert,
        to_user_id=2,
        transferred_by_user_id=7,
        reason="Automated test transfer.",
    )

    assert updated_alert.assigned_to_user_id == 2
    assert updated_alert.status == "active"

    assert history.alert_id == alert.id
    assert history.from_user_id == 7
    assert history.to_user_id == 2
    assert history.transferred_by_user_id == 7
    assert history.action == "transferred"
    assert history.reason == "Automated test transfer."

    history_entries = get_alert_handoff_history(
        db_session,
        alert_id=alert.id,
    )

    assert len(history_entries) == 1
    assert history_entries[0].to_user_id == 2


def test_transfer_to_same_assignee_is_rejected(db_session):
    """An alert cannot be transferred to its current assignee."""

    alert = make_test_alert(
        db_session,
        assigned_to_user_id=7,
    )

    with pytest.raises(ValueError):
        transfer_alert(
            db_session,
            alert=alert,
            to_user_id=7,
            transferred_by_user_id=7,
            reason="Attempted self-transfer.",
        )

    assert alert.assigned_to_user_id == 7
    assert get_alert_handoff_history(
        db_session,
        alert_id=alert.id,
    ) == []


def test_acknowledge_then_resolve(db_session):
    """Acknowledgement and resolution should persist independently."""

    alert = make_test_alert(
        db_session,
        assigned_to_user_id=7,
    )

    acknowledged = acknowledge_alert(
        db_session,
        alert=alert,
        user_id=7,
    )

    assert acknowledged.status == "acknowledged"
    assert acknowledged.acknowledged_by == 7
    assert acknowledged.acknowledged_at is not None

    resolved = resolve_alert(
        db_session,
        alert=acknowledged,
        user_id=7,
    )

    assert resolved.status == "resolved"
    assert resolved.resolved_by == 7
    assert resolved.resolved_at is not None
