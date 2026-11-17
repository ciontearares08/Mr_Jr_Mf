from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.db.models.field import Field
from api.db.models.field_member import FieldMember, FieldRole
from api.db.models.user import User

# A higher role may do everything that a lower role may do.
ROLE_RANK = {FieldRole.viewer: 0, FieldRole.owner: 1}


def require_role(
    field_id: int, user: User, db: Session, role: FieldRole
) -> tuple[Field, FieldRole]:
    """Return the field and the user's role on it, if the role is high enough.

    Non-members get 404, not 403, so nobody can find out which field IDs exist.
    """
    row = db.execute(
        select(Field, FieldMember.role)
        .join(FieldMember)
        .where(Field.id == field_id, FieldMember.user_id == user.id)
    ).one_or_none()
    if row is None or ROLE_RANK[row.role] < ROLE_RANK[role]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Field not found")
    return row.Field, row.role
