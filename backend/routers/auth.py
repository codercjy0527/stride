from fastapi import Depends
from sqlalchemy.orm import Session

from database import get_db
from db.user import User


def get_default_user(db: Session = Depends(get_db)) -> User:
    """Return the default single user (id=1). Auto-create on first run."""
    user = db.query(User).filter(User.id == 1).first()
    if not user:
        user = User(
            id=1,
            username="runner",
            email="runner@local",
            hashed_password="",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# Keep the old name so all routers still work without changes
get_current_user = get_default_user
