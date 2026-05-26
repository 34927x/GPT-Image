import json
import sys
import os

# Add root directory to path to import config
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from config import Account, accounts_col

def process_account_entry(cookies, source="unknown", label=None):
    """
    Centralized function to handle account entries.
    Validates cookies and either creates a new account or updates an existing one.
    Resets all error and limit flags on update.
    """
    if isinstance(cookies, str):
        try:
            cookies = json.loads(cookies)
        except Exception as e:
            return False, f"Invalid cookies format: not a valid JSON ({e})"
            
    if not isinstance(cookies, list) or not cookies:
        return False, "Invalid cookies format: must be a non-empty list"

    # Generate a label if none is provided
    if not label:
        # Try to find a unique label
        base_label = f"{source}-auto"
        count = accounts_col.count_documents({"source": source})
        label = f"{base_label}-{count + 1}"
        
        # Ensure it doesn't already exist to avoid unique constraint errors
        while accounts_col.find_one({"label": label}):
            count += 1
            label = f"{base_label}-{count + 1}"
    
    # Check if an account with this label already exists
    existing = accounts_col.find_one({"label": label})
    
    if existing:
        # Update existing account with new cookies and reset error counts/limits
        accounts_col.update_one(
            {"_id": existing["_id"]},
            {"$set": {
                "cookies": cookies,
                "source": source,
                "expired": False,
                "error_count": 0,
                "limited": False,
                "limit_reset_at": None,
                "limit_hit_at": None
            }}
        )
        return True, f"Updated existing account: {label}"
    else:
        try:
            # Create a new account
            Account.create(label=label, cookies=cookies, source=source)
            return True, f"Created new account: {label}"
        except Exception as e:
            return False, f"Database error during creation: {e}"
