from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.permissions import PERMISSIONS
from app.models.permission import Permission


def main():
    db = SessionLocal()

    try:
        created = 0
        existing = 0

        for name, description in PERMISSIONS.items():
            permission = db.scalar(
                select(Permission).where(
                    Permission.name == name
                )
            )

            if permission is not None:
                existing += 1
                continue

            db.add(
                Permission(
                    name=name,
                    description=description,
                    is_active=True,
                )
            )
            created += 1

        db.commit()

        print("Permission seed completed.")
        print("Created:", created)
        print("Already existing:", existing)
        print("Total catalog permissions:", len(PERMISSIONS))

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()