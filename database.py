# database.py
from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/valuations.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def ensure_db_schema():
    """Migração leve para bases SQLite existentes: adiciona modelo e detalhes caso faltem."""
    with engine.connect() as conn:
        from sqlalchemy import text
        try:
            result = conn.execute(text("PRAGMA table_info(valuations)")).fetchall()
            cols = [r[1] for r in result]
            if cols:
                if "modelo" not in cols:
                    conn.execute(text("ALTER TABLE valuations ADD COLUMN modelo VARCHAR DEFAULT 'dcf_fcff'"))
                if "detalhes" not in cols:
                    conn.execute(text("ALTER TABLE valuations ADD COLUMN detalhes TEXT"))
                conn.commit()
        except Exception:
            pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
