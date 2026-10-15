
from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.permissions import PERMISSIONS
from app.core.role_permissions import ROLE_PERMISSIONS
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission
from app.models.user import User


def main():
    db = SessionLocal()

    try:
        all_permissions = db.scalars(
            select(Permission).order_by(Permission.name)
        ).all()

        database_names = {
            permission.name for permission in all_permissions
        }

        print("\n=== PERMISSION CATALOG ===")
        print("Defined in code:", len(PERMISSIONS))
        print("Present in database:", len(database_names))
        print(
            "Missing from database:",
            sorted(set(PERMISSIONS) - database_names),
        )

        print("\n=== ROLE PERMISSIONS ===")

        for role_name, expected_list in ROLE_PERMISSIONS.items():
            role = db.scalar(
                select(Role).where(Role.name == role_name)
            )

            if role is None:
                print(f"\n{role_name}: ROLE MISSING")
                continue

            assigned = db.scalars(
                select(Permission)
                .join(
                    RolePermission,
                    RolePermission.permission_id == Permission.id,
                )
                .where(RolePermission.role_id == role.id)
                .order_by(Permission.name)
            ).all()

            actual_names = {p.name for p in assigned}
            expected_names = set(expected_list)

            print(f"\n{role_name}")
            print("Assigned:", len(actual_names))
            print("Expected:", len(expected_names))
            print("Missing assignments:", sorted(
                expected_names - actual_names
            ))
            print("Extra assignments:", sorted(
                actual_names - expected_names
            ))
            print("Inactive permissions:", sorted(
                p.name for p in assigned if not p.is_active
            ))

        print("\n=== USER ROLE ASSIGNMENTS ===")

        users = db.scalars(
            select(User).order_by(User.username)
        ).all()

        for user in users:
            role = db.get(Role, user.role_id)
            role_name = role.name if role else "MISSING ROLE"
            print(f"{user.username}: {role_name}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
