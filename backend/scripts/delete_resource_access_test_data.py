from sqlalchemy import delete, select

from app.core.database import SessionLocal
from app.models.bed import Bed
from app.models.department import Department
from app.models.hospital import Hospital
from app.models.room import Room
from app.models.user import User
from app.models.user_ward import UserWard
from app.models.ward import Ward


def main():
    db = SessionLocal()

    try:
        nurse = db.scalar(
            select(User).where(
                User.username == "resource_test_nurse"
            )
        )

        if nurse is not None:
            db.execute(
                delete(UserWard).where(
                    UserWard.user_id == nurse.id
                )
            )

            db.delete(nurse)

        icu_room = db.scalar(
            select(Room).where(
                Room.code == "ROOM-101-TEST"
            )
        )

        general_room = db.scalar(
            select(Room).where(
                Room.code == "ROOM-201-TEST"
            )
        )

        room_ids = [
            room.id
            for room in (icu_room, general_room)
            if room is not None
        ]

        if room_ids:
            db.execute(
                delete(Bed).where(
                    Bed.room_id.in_(room_ids)
                )
            )

        for room in (icu_room, general_room):
            if room is not None:
                db.delete(room)

        icu_ward = db.scalar(
            select(Ward).where(
                Ward.code == "ICU-WARD-TEST"
            )
        )

        general_ward = db.scalar(
            select(Ward).where(
                Ward.code == "GEN-WARD-TEST"
            )
        )

        for ward in (icu_ward, general_ward):
            if ward is not None:
                db.delete(ward)

        db.flush()

        icu_department = db.scalar(
            select(Department).where(
                Department.code == "ICU-TEST"
            )
        )

        general_department = db.scalar(
            select(Department).where(
                Department.code == "GEN-TEST"
            )
        )

        for department in (
            icu_department,
            general_department,
        ):
            if department is not None:
                db.delete(department)

        hospital = db.scalar(
            select(Hospital).where(
                Hospital.code == "EMPATH-TEST"
            )
        )

        if hospital is not None:
            db.delete(hospital)

        db.commit()

        print("Resource access test data cleanup completed.")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()