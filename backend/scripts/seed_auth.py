import os

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.permission import Permission
from app.models.role import Role
from app.models.user import User


ROLES = {
    "ADMIN": "System administrator",
    "NURSE": "Nursing staff",
    "DOCTOR": "Doctor",
    "RESEARCHER": "Research and audit user",
}


PERMISSIONS = {
    "users.read": "View users",
    "users.create": "Create users",
    "users.update": "Update users",
    "users.delete": "Deactivate or delete users",
    "roles.read": "View roles",
    "roles.manage": "Create and manage roles",
    "permissions.read": "View permissions",
    "permissions.manage": "Create and manage permissions",
}


def seed_roles(db):
    roles = {}

    for name, description in ROLES.items():
        role = db.scalar(
            select(Role).where(Role.name == name)
        )

        if role is None:
            role = Role(
                name=name,
                description=description,
            )
            db.add(role)
            db.flush()

        roles[name] = role

    return roles


def seed_permissions(db):
    permissions = {}

    for name, description in PERMISSIONS.items():
        permission = db.scalar(
            select(Permission).where(Permission.name == name)
        )

        if permission is None:
            permission = Permission(
                name=name,
                description=description,
            )
            db.add(permission)
            db.flush()

        permissions[name] = permission

    return permissions


def seed_admin(db, admin_role):
    user = db.scalar(
        select(User).where(User.username == "admin")
    )

    if user is None:
        initial_password = os.getenv(
            "EMPATH_ADMIN_INITIAL_PASSWORD"
        )

        if not initial_password:
            raise RuntimeError(
                "Set EMPATH_ADMIN_INITIAL_PASSWORD before "
                "creating the initial admin."
            )

        if len(initial_password) < 16:
            raise RuntimeError(
                "EMPATH_ADMIN_INITIAL_PASSWORD must be at "
                "least 16 characters long."
            )

        user = User(
            username="admin",
            email="admin@empath.local",
            role_id=admin_role.id,
            password_hash=hash_password(initial_password),
            full_name="EMPATH Administrator",
            is_active=True,
        )
        db.add(user)
        db.flush()

    return user


def main():
    db = SessionLocal()

    try:
        roles = seed_roles(db)
        permissions = seed_permissions(db)
        admin = seed_admin(db, roles["ADMIN"])

        db.commit()

        print("Authentication seed completed.")
        print("Roles:", len(roles))
        print("Permissions:", len(permissions))
        print("Admin username:", admin.username)
        print("Admin user ID:", admin.id)

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


if __name__ == "__main__":
    main()