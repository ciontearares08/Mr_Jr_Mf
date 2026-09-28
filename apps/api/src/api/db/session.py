import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

DATABASE_URL = os.environ["DATABASE_URL"]

engine = create_engine(DATABASE_URL)

session_local = sessionmaker(bind=engine)

def get_db() -> Generator[Session]:
    with session_local() as session:
        yield session
