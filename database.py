from config import DB_SERVER, DB_NAME, DB_USER, DB_PASSWORD
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

engine = create_engine(
    f"mssql+pyodbc://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_SERVER}/{DB_NAME}"
    "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes",
    poolclass=NullPool,
)

SessionLocal = sessionmaker(bind=engine)
