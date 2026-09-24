from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.role import Role
from app.models.user import User


def main():
    db = SessionLocal()

    try:
        role = db.scalar(
            select(Role).where(Role.name == "NURSE")
        )

        if role is None:
            raise RuntimeError("NURSE role does not exist")

        existing = db.scalar(
            select(User).where(
                User.username == "rbac_nurse_test"
            )
        )

        if existing:
            print("Test user already exists.")
            print("Username: rbac_nurse_test")
            print("Role: NURSE")
            return

        user = User(
            username="rbac_nurse_test",
            email="rbac_nurse_test@empath.dev",
            full_name="RBAC Nurse Test",
            role_id=role.id,
            password_hash=hash_password("NurseTest123!"),
            is_active=True,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        print("RBAC test user created.")
        print("User ID:", user.id)
        print("Username:", user.username)
        print("Role: NURSE")

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()