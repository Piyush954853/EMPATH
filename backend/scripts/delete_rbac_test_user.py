from sqlalchemy import delete

from app.core.database import SessionLocal
from app.models.user import User


def main():
    db = SessionLocal()

    try:
        result = db.execute(
            delete(User).where(
                User.username == "rbac_nurse_test"
            )
        )

        db.commit()

        print("RBAC test user cleanup completed.")
        print("Users deleted:", result.rowcount)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()