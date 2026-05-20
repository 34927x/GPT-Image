"""
Lightweight utility functions extracted from worker.py.
These functions do NOT depend on Playwright or any browser libraries,
so they can safely be imported on Heroku (or anywhere).
"""
import re
from datetime import datetime, timezone, timedelta

import config
from config import Account, accounts_col


def is_admin(user_id):
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
    from worker.entry import process_account_entry
    count = 0
    for item in data:
        if not item.get("cookies"):
            continue
        label = item.get("label", f"Imported-{count}")
        process_account_entry(item["cookies"], source="json_import", label=label)
        count += 1
    return count


def mark_expired(account_id):
    doc = accounts_col.find_one({"_id": account_id})
    if doc:
        name = doc.get("profile_name") or doc.get("label", "Unknown")
        accounts_col.delete_one({"_id": account_id})
        return name
    return None


def reset_limited_accounts():
    now = datetime.now(timezone.utc)
    count = accounts_col.update_many(
        {"limited": True, "limit_reset_at": {"$lt": now}},
        {"$set": {"limited": False, "limit_reset_at": None, "limit_hit_at": None, "error_count": 0}}
    )
    return count.modified_count


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
