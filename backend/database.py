from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

from config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_public():
    """Same as get_db but without auth dependency (public access)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    import db.user
    import db.training
    import db.checkin
    import db.metrics
    import db.activity
    import db.coros_token
    Base.metadata.create_all(bind=engine)
