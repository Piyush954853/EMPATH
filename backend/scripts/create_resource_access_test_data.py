from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.bed import Bed
from app.models.department import Department
from app.models.hospital import Hospital
from app.models.patient import Patient
from app.models.room import Room
from app.models.role import Role
from app.models.user import User
from app.models.user_ward import UserWard
from app.models.ward import Ward


def get_or_create(db, model, **filters):
    instance = db.scalar(
        select(model).filter_by(**filters)
    )

    if instance is not None:
        return instance

    instance = model(**filters)
    db.add(instance)
    db.flush()

    return instance


def main():
    db = SessionLocal()

    try:
        hospital = get_or_create(
            db,
            Hospital,
            name="EMPATH Test Hospital",
            code="EMPATH-TEST",
            address="Test Address",
            is_active=True,
        )

        icu_department = get_or_create(
            db,
            Department,
            hospital_id=hospital.id,
            name="ICU Department",
            code="ICU-TEST",
            is_active=True,
        )

        general_department = get_or_create(
            db,
            Department,
            hospital_id=hospital.id,
            name="General Department",
            code="GEN-TEST",
            is_active=True,
        )

        icu_ward = get_or_create(
            db,
            Ward,
            department_id=icu_department.id,
            name="ICU Ward",
            code="ICU-WARD-TEST",
            is_active=True,
        )

        general_ward = get_or_create(
            db,
            Ward,
            department_id=general_department.id,
            name="General Ward",
            code="GEN-WARD-TEST",
            is_active=True,
        )

        icu_room = get_or_create(
            db,
            Room,
            ward_id=icu_ward.id,
            name="Room 101",
            code="ROOM-101-TEST",
            is_active=True,
        )

        general_room = get_or_create(
            db,
            Room,
            ward_id=general_ward.id,
            name="Room 201",
            code="ROOM-201-TEST",
            is_active=True,
        )

        icu_bed = get_or_create(
            db,
            Bed,
            room_id=icu_room.id,
            name="Bed 101-A",
            code="BED-101-A-TEST",
            is_occupied=False,
            is_active=True,
        )

        general_bed = get_or_create(
            db,
            Bed,
            room_id=general_room.id,
            name="Bed 201-A",
            code="BED-201-A-TEST",
            is_occupied=False,
            is_active=True,
        )

        nurse_role = db.scalar(
            select(Role).where(
                Role.name == "NURSE"
            )
        )

        if nurse_role is None:
            raise RuntimeError("NURSE role does not exist")

        nurse = db.scalar(
            select(User).where(
                User.username == "resource_test_nurse"
            )
        )

        if nurse is None:
            nurse = User(
                username="resource_test_nurse",
                email="resource_test_nurse@empath.dev",
                full_name="Resource Access Test Nurse",
                role_id=nurse_role.id,
                password_hash=hash_password(
                    "ResourceTest123!"
                ),
                is_active=True,
            )
            db.add(nurse)
            db.flush()

        assignment = db.scalar(
            select(UserWard).where(
                UserWard.user_id == nurse.id,
                UserWard.ward_id == icu_ward.id,
            )
        )

        if assignment is None:
            db.add(
                UserWard(
                    user_id=nurse.id,
                    ward_id=icu_ward.id,
                )
            )

        db.commit()

        print("Resource access test data created.")
        print("Hospital ID:", hospital.id)
        print("ICU Department ID:", icu_department.id)
        print("General Department ID:", general_department.id)
        print("ICU Ward ID:", icu_ward.id)
        print("General Ward ID:", general_ward.id)
        print("ICU Room ID:", icu_room.id)
        print("General Room ID:", general_room.id)
        print("ICU Bed ID:", icu_bed.id)
        print("General Bed ID:", general_bed.id)
        print("Test nurse ID:", nurse.id)
        print("Test nurse username:", nurse.username)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()