import os
import sys
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(BASE_DIR)

from sqlalchemy import text

from app.database import engine, create_tables


create_tables()

with engine.connect() as connection:
    result = connection.execute(text("SELECT 1"))
    print(result.scalar())

print("Database tables created!")
