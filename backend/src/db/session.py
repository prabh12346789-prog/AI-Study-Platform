from sqlalchemy.orm import sessionmaker
from src.db.database import engine

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)