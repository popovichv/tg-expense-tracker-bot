import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TG_TOKEN")
DB_SERVER = os.getenv("DB_SERVER")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
