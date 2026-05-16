import json
from datetime import datetime, timezone, timedelta
from db import accounts_col
from models import Account

def is_admin(user_id):
    import config
    return user_id in config.ADMIN_IDS

def export_accounts():
    docs = Account.get_all()
    data = []
    for d in docs:
        data.append({
            "label": d["label"],
            "cookies": d["cookies"],
            "created_at": d["created_at"].isoformat() if d.get("created_at") else None
        })
    return data

def import_accounts(data):
    count = 0
    for item in data:
        if not item.get("cookies"):
            continue
        label = item.get("label", f"Imported-{count}")
        exists = accounts_col.find_one({"label": label})
        if exists:
            label = f"{label}-{count}"
        Account.create(label, item["cookies"])
        count += 1
    return count

def get_next_account():
    docs = list(accounts_col.find().sort("last_used", 1))
    if not docs:
        return None
    for d in docs:
        errs = d.get("error_count", 0)
        if errs < 3:
            return d
    accounts_col.update_many({}, {"$set": {"error_count": 0}})
    return docs[0]

def mark_error(account_id):
    accounts_col.update_one({"_id": account_id}, {"$inc": {"error_count": 1}})

def mark_success(account_id):
    accounts_col.update_one({"_id": account_id}, {
        "$set": {"last_used": datetime.now(timezone.utc), "error_count": 0}
    })

def mark_expired(account_id):
    accounts_col.update_one({"_id": account_id}, {
        "$set": {"expired": True, "last_used": datetime.now(timezone.utc)}
    })

def get_expired_accounts():
    return list(accounts_col.find({"expired": True}))

def get_session_status():
    docs = Account.get_all()
    now = datetime.now(timezone.utc)
    lines = []
    for i, d in enumerate(docs):
        label = d.get("label", f"#{i+1}")
        last = d.get("last_used") or d.get("created_at")
        expired = d.get("expired", False)
        errs = d.get("error_count", 0)
        hours_since = (now - last).total_seconds() / 3600 if last else 0
        status = "❌" if expired else ("⚠️" if errs > 0 else "✅")
        lines.append(f"{status} {i+1}. `{label}` — {hours_since:.0f}h ago")
    return lines
