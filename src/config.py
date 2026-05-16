import os

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB = os.getenv("MONGO_DB", "gpt_rotator")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "0").split(",") if x]

COOKIE_DOMAINS = ["chatgpt.com", ".openai.com"]
RATE_LIMIT_THRESHOLD = 2
MAX_QUEUE_PER_USER = 50
SESSION_CHECK_HOURS = 6
