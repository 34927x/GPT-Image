import asyncio
from pymongo import MongoClient
import config

_client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)

db = _client[config.MONGO_DB]

accounts_col = db["accounts"]
queue_col = db["queue"]
settings_col = db["settings"]
sessions_col = db["sessions"]

async def init_db():
    try:
        await asyncio.get_event_loop().run_in_executor(None, lambda: _client.admin.command('ping'))
        await asyncio.get_event_loop().run_in_executor(None, lambda: accounts_col.create_index("label", unique=True, sparse=True))
        await asyncio.get_event_loop().run_in_executor(None, lambda: queue_col.create_index("status"))
        await asyncio.get_event_loop().run_in_executor(None, lambda: queue_col.create_index("created_at"))
        await asyncio.get_event_loop().run_in_executor(None, lambda: settings_col.create_index("key", unique=True))
    except Exception as e:
        print(f"[db] MongoDB init error: {e}")
        raise

def get_setting(key, default=None):
    doc = settings_col.find_one({"key": key})
    return doc["value"] if doc else default

def set_setting(key, value):
    settings_col.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)
