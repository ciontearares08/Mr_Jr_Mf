# This script is used to delete the database schema and recreate it.
import os

from sqlalchemy import create_engine, text

engine = create_engine(os.environ.get("DATABASE_URL"))

with engine.begin() as conn:
    conn.execute(text("DROP SCHEMA public CASCADE;"))
    conn.execute(text("CREATE SCHEMA public;"))

