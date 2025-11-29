import os
from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
from config import DATABASE_URL

""" Get the database URL from environment variables """
SQLALCHEMY_DATABASE_URL = DATABASE_URL

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_size=20,
    max_overflow=30,
    pool_timeout=30,
    pool_recycle=1800,
    pool_pre_ping=True
)

""" Create a sessionmaker factory that will create new SessionLocal instances """
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

""" Initialize the FastAPI application """
app = FastAPI()

def get_db():
    """
    Dependency that provides a database session to the request.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()