import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

engine = create_engine(
    f"mssql+pyodbc://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{os.getenv('DB_SERVER')}/{os.getenv('DB_NAME')}"
    "?driver=ODBC+Driver+18+for+SQL+Server&timeout=30",
    poolclass=NullPool,
)

SessionLocal = sessionmaker(bind=engine)
