"""
Database initialization script.
Run: python init_db.py
"""
import sys
import os

# Load .env from project root before importing app modules
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
if os.path.exists(env_path):
    load_dotenv(env_path, override=True)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import init_db, engine
from models import Base


def main():
    print("Initializing database...")
    print(f"Engine URL: {engine.url}")
    init_db()
    print("All tables created successfully.")

    # Verify tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables: {tables}")


if __name__ == '__main__':
    main()
