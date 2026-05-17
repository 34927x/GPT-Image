from datetime import datetime, timezone
from db import accounts_col, queue_col, sessions_col

class Account:
    @staticmethod
    def create(label, cookies, source="manual"):
        return accounts_col.insert_one({
            "label": label,
            "profile_name": label,
            "cookies": cookies,
            "source": source,
            "active": False,
            "limited": False,
            "limit_reset_at": None,
            "limit_hit_at": None,
            "first_loaded_at": datetime.now(timezone.utc),
            "created_at": datetime.now(timezone.utc),
            "last_used": None,
            "error_count": 0,
            "expired": False
        })

    @staticmethod
    def get_all():
        return list(accounts_col.find())

    @staticmethod
    def get_active():
        return accounts_col.find_one({"active": True})

    @staticmethod
    def set_active(index_or_id):
        accounts_col.update_many({}, {"$set": {"active": False}})
        if isinstance(index_or_id, int):
            docs = list(accounts_col.find().sort("created_at", 1))
            if index_or_id < len(docs):
                accounts_col.update_one({"_id": docs[index_or_id]["_id"]}, {"$set": {"active": True}})
                return docs[index_or_id]
        else:
            accounts_col.update_one({"_id": index_or_id}, {"$set": {"active": True}})
            return accounts_col.find_one({"_id": index_or_id})

    @staticmethod
    def remove(index):
        docs = list(accounts_col.find().sort("created_at", 1))
        if index < len(docs):
            accounts_col.delete_one({"_id": docs[index]["_id"]})

    @staticmethod
    def count():
        return accounts_col.count_documents({})

class Queue:
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_DONE = "done"
    STATUS_FAIL = "fail"

    @staticmethod
    def add(prompt, user_id, image_size="1:1", bulk_count=1):
        if isinstance(prompt, list):
            return [queue_col.insert_one({
                "prompts": prompt,
                "is_bulk": True,
                "status": Queue.STATUS_PENDING,
                "user_id": user_id,
                "image_size": image_size,
                "created_at": datetime.now(timezone.utc),
                "processed_at": None
            })]
        items = []
        for i in range(bulk_count):
            items.append(queue_col.insert_one({
                "prompt": prompt,
                "batch_index": i,
                "batch_total": bulk_count,
                "status": Queue.STATUS_PENDING,
                "user_id": user_id,
                "image_size": image_size,
                "image_url": None,
                "error": None,
                "created_at": datetime.now(timezone.utc),
                "processed_at": None
            }))
        return items

    @staticmethod
    def get_pending():
        return queue_col.find_one({"status": Queue.STATUS_PENDING})

    @staticmethod
    def get_pending_count():
        return queue_col.count_documents({"status": Queue.STATUS_PENDING})

    @staticmethod
    def get_all():
        return list(queue_col.find().sort("created_at", 1))

    @staticmethod
    def get_user_queue(user_id):
        return list(queue_col.find({"user_id": user_id}).sort("created_at", 1))

    @staticmethod
    def update_status(qid, status, image_url=None, error=None):
        update = {"status": status, "processed_at": datetime.now(timezone.utc)}
        if image_url: update["image_url"] = image_url
        if error: update["error"] = error
        queue_col.update_one({"_id": qid}, {"$set": update})

    @staticmethod
    def stats():
        total = queue_col.count_documents({})
        done = queue_col.count_documents({"status": Queue.STATUS_DONE})
        fail = queue_col.count_documents({"status": Queue.STATUS_FAIL})
        pending = queue_col.count_documents({"status": Queue.STATUS_PENDING})
        processing = queue_col.count_documents({"status": Queue.STATUS_PROCESSING})
        return {"total": total, "done": done, "fail": fail, "pending": pending, "processing": processing}

    @staticmethod
    def clear():
        queue_col.delete_many({})
