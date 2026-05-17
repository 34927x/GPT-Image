import json, re
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
    now = datetime.now(timezone.utc)
    docs = list(accounts_col.find().sort("last_used", 1))
    limited_accounts = []
    for d in docs:
        if d.get("expired"):
            continue
        if d.get("limited"):
            reset_at = d.get("limit_reset_at")
            if reset_at and reset_at > now:
                left = (reset_at - now).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                limited_accounts.append({
                    "label": d.get("profile_name") or d.get("label", "Unknown"),
                    "reset_at": reset_at,
                    "hours_left": h,
                    "minutes_left": m
                })
                continue
            accounts_col.update_one({"_id": d["_id"]}, {"$set": {"limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}})
        errs = d.get("error_count", 0)
        if errs < 3:
            return d
    if limited_accounts:
        return {"_limited_info": True, "accounts": limited_accounts}
    accounts_col.update_many({}, {"$set": {"error_count": 0}})
    return None

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

def mark_limited(account_id, reset_at):
    accounts_col.update_one({"_id": account_id}, {
        "$set": {
            "limited": True,
            "limit_reset_at": reset_at,
            "limit_hit_at": datetime.now(timezone.utc),
            "last_used": datetime.now(timezone.utc)
        }
    })

def update_profile_name(account_id, name):
    if name:
        accounts_col.update_one({"_id": account_id}, {"$set": {"profile_name": name}})

def reset_limited_accounts():
    now = datetime.now(timezone.utc)
    count = accounts_col.update_many(
        {"limited": True, "limit_reset_at": {"$lt": now}},
        {"$set": {"limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}}
    )
    return count.modified_count

def get_expired_accounts():
    return list(accounts_col.find({"expired": True}))

def add_manual_account(cookies, label=None):
    if isinstance(cookies, str):
        cookies = json.loads(cookies)
    if not isinstance(cookies, list) or not cookies:
        return False, "Invalid cookies format"
    label = label or f"manual-{len(list(accounts_col.find()))+1}"
    account = accounts_col.find_one({"label": label})
    if account:
        accounts_col.update_one(
            {"_id": account["_id"]},
            {"$set": {"cookies": cookies, "source": "manual", "expired": False, "error_count": 0}}
        )
        return True, f"Updated: {label}"
    Account.create(label, cookies, source="manual")
    return True, f"Created: {label}"

def get_session_status():
    docs = Account.get_all()
    now = datetime.now(timezone.utc)
    lines = []
    for i, d in enumerate(docs):
        name = d.get("profile_name") or d.get("label", f"#{i+1}")
        last = d.get("last_used") or d.get("created_at")
        if last and last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        expired = d.get("expired", False)
        limited = d.get("limited", False)
        errs = d.get("error_count", 0)
        hours_since = (now - last).total_seconds() / 3600 if last else 0
        first_loaded = d.get("first_loaded_at")
        if first_loaded and first_loaded.tzinfo is None:
            first_loaded = first_loaded.replace(tzinfo=timezone.utc)
        is_fresh = first_loaded and (now - first_loaded).total_seconds() < 3600
        limit_hit_at = d.get("limit_hit_at")
        if limit_hit_at and limit_hit_at.tzinfo is None:
            limit_hit_at = limit_hit_at.replace(tzinfo=timezone.utc)
        if expired:
            status = "❌ Expired"
        elif limited:
            reset_at = d.get("limit_reset_at")
            if reset_at:
                left = (reset_at - now).total_seconds()
                h = int(left // 3600)
                m = int((left % 3600) // 60)
                status = f"⏳ Limit ({h}h {m}m left)"
            else:
                status = "⏳ Limited"
        elif errs > 0:
            status = "⚠️ Errors"
        else:
            status = "✅ Active"
        fresh_tag = " 🆕" if is_fresh else ""
        lines.append(f"{i+1}. `{name}` — {status}{fresh_tag} — {hours_since:.0f}h ago")
    return lines

def parse_limit_reset_time(body):
    m = re.search(r'resets in (?:about )?(?:(\d+)\s*hours?)?\s*(?:and\s*)?(?:(\d+)\s*minutes?)?', body.lower())
    if m:
        hours = int(m.group(1)) if m.group(1) else 0
        mins = int(m.group(2)) if m.group(2) else 0
        if hours > 0 or mins > 0:
            return datetime.now(timezone.utc) + timedelta(hours=hours, minutes=mins)
    m2 = re.search(r'(\d+)\s*hours?\s*(\d+)\s*minutes?', body.lower())
    if m2:
        return datetime.now(timezone.utc) + timedelta(hours=int(m2.group(1)), minutes=int(m2.group(2)))
    return None
