from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from backend.app.config import settings

import os
import logging

logger = logging.getLogger("retry_backend")

# Resolve SQLite database path to print the absolute location
db_url = settings.DATABASE_URL
if db_url.startswith("sqlite"):
    if db_url.startswith("sqlite:///"):
        db_path = db_url[10:]
    else:
        db_path = db_url[9:]
    abs_path = os.path.abspath(db_path)
    logger.info(f"Database Engine initialized with URL: {db_url}")
    logger.info(f"Resolved database absolute path: {abs_path}")
    print(f"DATABASE INITIALIZATION: Engine using SQLite database at: {abs_path}")
else:
    logger.info(f"Database Engine initialized with URL: {db_url}")
    print(f"DATABASE INITIALIZATION: Engine using database URL: {db_url}")

# For SQLite, check_same_thread is required, for Postgres it is not.
connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
