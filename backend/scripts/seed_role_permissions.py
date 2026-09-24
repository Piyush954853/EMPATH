from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.role_permissions import ROLE_PERMISSIONS
from app.models.permission import Permission
from app.models.role import Role
from app.models.role_permission import RolePermission


def main():
    db = SessionLocal()

    try:
        created = 0
        existing = 0

        for role_name, permission_names in ROLE_PERMISSIONS.items():
            role = db.scalar(
                select(Role).where(
                    Role.name == role_name
                )
            )

            if role is None:
                raise RuntimeError(
                    f"Role does not exist: {role_name}"
                )

            for permission_name in permission_names:
                permission = db.scalar(
                    select(Permission).where(
                        Permission.name == permission_name
                    )
                )

                if permission is None:
                    raise RuntimeError(
                        f"Permission does not exist: {permission_name}"
                    )

                role_permission = db.scalar(
                    select(RolePermission).where(
                        RolePermission.role_id == role.id,
                        RolePermission.permission_id == permission.id,
                    )
                )

                if role_permission is not None:
                    existing += 1
                    continue

                db.add(
                    RolePermission(
                        role_id=role.id,
                        permission_id=permission.id,
                    )
                )
                created += 1

        db.commit()

        print("Role permission seed completed.")
        print("Created:", created)
        print("Already existing:", existing)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()