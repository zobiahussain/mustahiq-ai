from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

if settings.portal_demo_mode:
    Path(settings.portal_demo_database).parent.mkdir(parents=True, exist_ok=True)
    database_url = 'sqlite:///' + settings.portal_demo_database.replace('\\', '/')
else:
    database_url = settings.database_url
    if not database_url:
        raise RuntimeError('Set DATABASE_URL for Supabase, or PORTAL_DEMO_MODE=true for the isolated synthetic demo.')
engine = create_engine(database_url, pool_pre_ping=True, **({'connect_args': {'check_same_thread': False}} if settings.portal_demo_mode else {}))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
