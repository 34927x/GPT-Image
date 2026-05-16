from pymongo import MongoClient
import config

client = MongoClient(config.MONGO_URI)
db = client[config.MONGO_DB]

accounts_col = db["accounts"]
queue_col = db["queue"]
settings_col = db["settings"]
sessions_col = db["sessions"]

def init_db():
    accounts_col.create_index("label", unique=True, sparse=True)
    queue_col.create_index("status")
    queue_col.create_index("created_at")
    sessions_col.create_index("user_id", unique=True)
    settings_col.create_index("key", unique=True)

def get_setting(key, default=None):
    doc = settings_col.find_one({"key": key})
    return doc["value"] if doc else default

def set_setting(key, value):
    settings_col.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)
