import os
from urllib.parse import quote_plus

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

load_dotenv()


def _build_db_url() -> str:
    database_url = os.getenv("SUPABASE_DB_URL")
    if database_url:
        return database_url

    password = os.getenv("SUPA_PASSWORD")
    project_ref = os.getenv("SUPABASE_PROJECT_REF")
    if password and project_ref:
        # project ref is the first label of the Supabase URL host
        # project_ref = urlparse(supabase_url).hostname.split(".")[0]
        return (
            f"postgresql+psycopg2://postgres:{quote_plus(password)}"
            f"@db.{project_ref}.supabase.co:5432/postgres"
        )

    raise RuntimeError(
        "Set SUPABASE_URL, or SUPABASE_DB_URL and SUPA_PASSWORD, in the environment"
    )


DATABASE_URL = _build_db_url()

# pool_pre_ping avoids stale connections dropped by Supabase's pooler
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
