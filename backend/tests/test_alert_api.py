from types import SimpleNamespace



import pytest

from fastapi.testclient import TestClient

from sqlalchemy import create_engine

from sqlalchemy.orm import sessionmaker

from sqlalchemy.pool import StaticPool



import app.models  # noqa: F401 - Register application models

from app.api import alert as alert_api

from app.api.dependencies import get_current_user

from app.core.database import Base, get_db

from app.main import app

from app.models.alert import Alert

from app.models.event import Event

from app.models.role import Role

from app.models.user import User





def iter_router_routes(router, seen=None):

    """

    Recursively yield routes from a router and routers nested inside it.



    This also handles FastAPI versions that represent included routers

    using internal wrapper objects rather than exposing paths directly.

    """

    if seen is None:

        seen = set()



    if router is None or id(router) in seen:

        return



    seen.add(id(router))



    for route in getattr(router, "routes", []):

        yield route



        # Explore nested/included routers when present.

        for attribute in (

            "original_router",

            "included_router",

            "router",

        ):

            nested_router = getattr(route, attribute, None)



            if nested_router is not None and nested_router is not router:

                yield from iter_router_routes(nested_router, seen)





def iter_dependencies(dependant, seen=None):

    """Recursively yield dependencies in a FastAPI dependency tree."""

    if seen is None:

        seen = set()



    if dependant is None or id(dependant) in seen:

        return



    seen.add(id(dependant))



    for dependency in getattr(dependant, "dependencies", []):

        yield dependency

        yield from iter_dependencies(dependency, seen)





@pytest.fixture

def alert_api_env():

    """

    Provide an isolated in-memory SQLite database for API workflow tests.



    Authentication is replaced with a controlled test identity.

    Route-level permission guards from app.api.permissions are overridden

    so the tests can reach and verify alert transfer business rules.



    These tests do not verify JWT tokens, passwords, or production

    resource-scope enforcement. Those require separate tests.

    """



    engine = create_engine(

        "sqlite://",

        connect_args={"check_same_thread": False},

        poolclass=StaticPool,

    )



    db = None

    client = None

    old_overrides = app.dependency_overrides.copy()



    try:

        Base.metadata.create_all(bind=engine)



        TestSession = sessionmaker(

            bind=engine,

            autoflush=False,

            autocommit=False,

            expire_on_commit=False,

        )



        db = TestSession()



        # ---------------------------------------------------------

        # 1. Create roles

        # ---------------------------------------------------------

        nurse_role = Role(

            name="NURSE",

            description="Test nurse role",

            is_active=True,

        )



        doctor_role = Role(

            name="DOCTOR",

            description="Test doctor role",

            is_active=True,

        )



        db.add_all([nurse_role, doctor_role])

        db.commit()

        db.refresh(nurse_role)

        db.refresh(doctor_role)



        # ---------------------------------------------------------

        # 2. Create users

        # ---------------------------------------------------------

        nurse_from = User(

            username="api_nurse_from",

            email="api_nurse_from@example.test",

            full_name="API Nurse From",

            role_id=nurse_role.id,

            password_hash="test-only-unused-hash",

            is_active=True,

        )



        nurse_to = User(

            username="api_nurse_to",

            email="api_nurse_to@example.test",

            full_name="API Nurse To",

            role_id=nurse_role.id,

            password_hash="test-only-unused-hash",

            is_active=True,

        )



        doctor = User(

            username="api_doctor",

            email="api_doctor@example.test",

            full_name="API Doctor",

            role_id=doctor_role.id,

            password_hash="test-only-unused-hash",

            is_active=True,

        )



        db.add_all([nurse_from, nurse_to, doctor])

        db.commit()



        db.refresh(nurse_from)

        db.refresh(nurse_to)

        db.refresh(doctor)



        # ---------------------------------------------------------

        # 3. Create a test event and an active alert

        # ---------------------------------------------------------

        event = Event(

            event_type="alert_handoff_test",

            source_type="manual_test",

            severity="medium",

            status="test",

            camera_id=None,

            patient_id=None,

            confidence=None,

            description="Test-only API event.",

            metadata_json='{"test_only": true}',

        )



        db.add(event)

        db.commit()

        db.refresh(event)



        alert = Alert(

            event_id=event.id,

            priority="medium",

            status="active",

            title="TEST - API Handoff",

            message="Test-only alert.",

            summary="Test-only summary.",

            assigned_to_user_id=nurse_from.id,

        )



        db.add(alert)

        db.commit()

        db.refresh(alert)



        # State can be changed by individual tests.

        state = {

            "current_user": nurse_from,

            "resource_access_user_ids": {

                nurse_from.id,

                nurse_to.id,

            },

        }



        # ---------------------------------------------------------

        # 4. Set up isolated database and test identity overrides

        # ---------------------------------------------------------

        def override_get_db():

            yield db



        def override_current_user():

            return state["current_user"]



        app.dependency_overrides[get_db] = override_get_db

        app.dependency_overrides[get_current_user] = (

            override_current_user

        )



        # ---------------------------------------------------------

        # 5. Find and override permission guard dependencies

        # ---------------------------------------------------------

        permission_override_count = 0

        visited_dependencies = set()



        # Inspect both the alert router and the application's included

        # routers. This handles nested-router layouts across FastAPI

        # versions.

        route_sources = (

            alert_api.router,

            app,

        )



        visited_routes = set()



        for router in route_sources:

            for route in iter_router_routes(router):

                if id(route) in visited_routes:

                    continue



                visited_routes.add(id(route))



                dependant = getattr(route, "dependant", None)

                if dependant is None:

                    continue



                for dependency in iter_dependencies(dependant):

                    call = getattr(dependency, "call", None)



                    if call is None or not callable(call):

                        continue



                    if id(call) in visited_dependencies:

                        continue



                    visited_dependencies.add(id(call))



                    module_name = getattr(call, "__module__", "")

                    function_name = getattr(call, "__name__", "")



                    # Only override permission guards defined in the

                    # app's permission module. Do not override the

                    # endpoint handler or unrelated dependencies.

                    is_permission_guard = (

                        module_name == "app.api.permissions"

                        and function_name == "permission_dependency"

                    )



                    if is_permission_guard:

                        app.dependency_overrides[call] = (

                            override_current_user

                        )

                        permission_override_count += 1



        # ---------------------------------------------------------

        # 6. Replace resource-scope checking for these focused tests

        # ---------------------------------------------------------

        def fake_can_access_alert(_db, user, _alert):

            return (

                user.id in state["resource_access_user_ids"]

            )



        # The alert API module calls this function. This replacement

        # simulates resource access; it does not test the real

        # can_access_camera/can_access_bed implementation.

        alert_can_access_original = alert_api.can_access_alert

        alert_api.can_access_alert = fake_can_access_alert



        client = TestClient(app)



        yield SimpleNamespace(

            client=client,

            db=db,

            state=state,

            nurse_from=nurse_from,

            nurse_to=nurse_to,

            doctor=doctor,

            alert=alert,

            permission_override_count=permission_override_count,

        )



    finally:

        # Restore global application state even if a test fails.

        if client is not None:

            client.close()



        # Restore the original alert resource checker if it was changed.

        if "alert_can_access_original" in locals():

            alert_api.can_access_alert = alert_can_access_original



        app.dependency_overrides.clear()

        app.dependency_overrides.update(old_overrides)



        if db is not None:

            db.close()



        Base.metadata.drop_all(bind=engine)

        engine.dispose()





def test_transfer_api_updates_assignment_and_history(alert_api_env):

    env = alert_api_env

    env.state["current_user"] = env.nurse_from



    response = env.client.post(

        f"/alerts/{env.alert.id}/transfer",

        json={

            "to_user_id": env.nurse_to.id,

            "reason": "API integration test transfer.",

        },

    )



    assert response.status_code == 200, response.text



    payload = response.json()



    assert payload["assigned_to_user_id"] == env.nurse_to.id

    assert payload["status"] == "active"



    history_response = env.client.get(

        f"/alerts/{env.alert.id}/history"

    )



    assert history_response.status_code == 200, history_response.text



    history = history_response.json()



    assert len(history) == 1

    assert history[0]["from_user_id"] == env.nurse_from.id

    assert history[0]["to_user_id"] == env.nurse_to.id

    assert history[0]["transferred_by_user_id"] == env.nurse_from.id

    assert history[0]["action"] == "transferred"

    assert history[0]["reason"] == "API integration test transfer."





def test_transfer_api_rejects_non_nurse(alert_api_env):

    env = alert_api_env



    env.state["current_user"] = env.doctor

    env.state["resource_access_user_ids"].add(env.doctor.id)



    response = env.client.post(

        f"/alerts/{env.alert.id}/transfer",

        json={

            "to_user_id": env.nurse_to.id,

            "reason": "Doctor role should not transfer in this workflow.",

        },

    )



    assert response.status_code == 403

    assert response.json()["detail"] == (

        "Only active Nurses can assign or transfer alerts."

    )





def test_transfer_api_rejects_unassigned_resource_access_for_recipient(

    alert_api_env,

):

    env = alert_api_env



    env.state["current_user"] = env.nurse_from



    # The sender can access the alert, but the recipient cannot.

    env.state["resource_access_user_ids"] = {

        env.nurse_from.id,

    }



    response = env.client.post(

        f"/alerts/{env.alert.id}/transfer",

        json={

            "to_user_id": env.nurse_to.id,

            "reason": "Recipient scope test.",

        },

    )



    assert response.status_code == 403

    assert "receiving Nurse does not have access" in (

        response.json()["detail"]

    )



    # A rejected transfer must not create a history record.

    history_response = env.client.get(

        f"/alerts/{env.alert.id}/history"

    )



    assert history_response.status_code == 200

    assert history_response.json() == []





def test_transfer_api_rejects_transfer_by_non_assignee(alert_api_env):

    env = alert_api_env



    # The alert is assigned to nurse_from, not nurse_to.

    env.state["current_user"] = env.nurse_to



    response = env.client.post(

        f"/alerts/{env.alert.id}/transfer",

        json={

            "to_user_id": env.nurse_from.id,

            "reason": "Non-assignee must not transfer this alert.",

        },

    )



    assert response.status_code == 403

    assert response.json()["detail"]



def test_eligible_nurses_api_returns_accessible_other_nurses(

    alert_api_env,

):

    env = alert_api_env

    env.state["current_user"] = env.nurse_from



    response = env.client.get(

        f"/alerts/{env.alert.id}/eligible-nurses"

    )



    assert response.status_code == 200, response.text



    payload = response.json()



    assert len(payload) == 1

    assert payload[0]["user_id"] == env.nurse_to.id

    assert payload[0]["username"] == env.nurse_to.username

# -------------------------------------------------------------
# Alert lifecycle API regression tests
# -------------------------------------------------------------

def test_acknowledge_api_updates_status_and_audit_fields(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from

    response = env.client.post(f"/alerts/{env.alert.id}/acknowledge")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "acknowledged"

    saved_alert = env.db.get(Alert, env.alert.id)
    assert saved_alert is not None
    assert saved_alert.status == "acknowledged"
    assert saved_alert.acknowledged_by == env.nurse_from.id
    assert saved_alert.acknowledged_at is not None


def test_resolve_api_resolves_active_alert_and_records_user(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from

    response = env.client.post(f"/alerts/{env.alert.id}/resolve")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"

    saved_alert = env.db.get(Alert, env.alert.id)
    assert saved_alert is not None
    assert saved_alert.status == "resolved"
    assert saved_alert.resolved_by == env.nurse_from.id
    assert saved_alert.resolved_at is not None


def test_resolve_api_accepts_acknowledged_alert(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from
    env.alert.status = "acknowledged"
    env.alert.acknowledged_by = env.nurse_from.id
    env.db.commit()

    response = env.client.post(f"/alerts/{env.alert.id}/resolve")

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "resolved"

    saved_alert = env.db.get(Alert, env.alert.id)
    assert saved_alert is not None
    assert saved_alert.resolved_by == env.nurse_from.id
    assert saved_alert.resolved_at is not None


def test_dismiss_api_dismisses_active_alert(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from

    response = env.client.post(f"/alerts/{env.alert.id}/dismiss")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "dismissed"
    assert payload["dismissed_by"] == env.nurse_from.id
    assert payload["dismissed_at"] is not None

    saved_alert = env.db.get(Alert, env.alert.id)
    assert saved_alert is not None
    assert saved_alert.status == "dismissed"
    assert saved_alert.dismissed_by == env.nurse_from.id
    assert saved_alert.dismissed_at is not None


def test_dismiss_api_dismisses_acknowledged_alert(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from
    env.alert.status = "acknowledged"
    env.alert.acknowledged_by = env.nurse_from.id
    env.db.commit()

    response = env.client.post(f"/alerts/{env.alert.id}/dismiss")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["status"] == "dismissed"
    assert payload["dismissed_by"] == env.nurse_from.id
    assert payload["dismissed_at"] is not None

    saved_alert = env.db.get(Alert, env.alert.id)
    assert saved_alert is not None
    assert saved_alert.status == "dismissed"
    assert saved_alert.dismissed_by == env.nurse_from.id
    assert saved_alert.dismissed_at is not None


def test_dismiss_api_rejects_resolved_alert(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from
    env.alert.status = "resolved"
    env.db.commit()

    response = env.client.post(f"/alerts/{env.alert.id}/dismiss")

    assert response.status_code == 409, response.text
    assert "Only active or acknowledged alerts can be dismissed" in response.json()["detail"]


def test_acknowledge_api_rejects_already_acknowledged_alert(alert_api_env):
    env = alert_api_env
    env.state["current_user"] = env.nurse_from

    first_response = env.client.post(f"/alerts/{env.alert.id}/acknowledge")
    assert first_response.status_code == 200, first_response.text

    second_response = env.client.post(f"/alerts/{env.alert.id}/acknowledge")
    assert second_response.status_code == 409, second_response.text
    assert "Only active alerts can be acknowledged" in second_response.json()["detail"]