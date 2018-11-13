import os
from dotenv import load_dotenv
from pathlib import Path  # python3 only
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

TOKEN = os.getenv('TELEGRAM_TOKEN', 'token')
ADMIN = os.getenv('ADMIN_USER', 'admin')
STATS = os.getenv('STATS_FILE', 'file')
RANKING_DB = os.getenv('SQLITE_FILE', 'sqlfile')
LOGGING_PATH = os.getenv('LOGGING_PATH', 'log')
SPECTATORS_GROUP = os.getenv('SPECTATORS_GROUP', 'group')
SPECTATORS_JOIN_URL = os.getenv('SPECTATORS_JOIN_URL', 'url')
