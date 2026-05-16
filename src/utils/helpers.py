import re, time, hashlib
from datetime import datetime, timezone

def sanitize_filename(name):
    name = re.sub(r'[^\w\s-]', '', name)
    name = re.sub(r'[-\s]+', '-', name)
    return name.strip('-').lower()[:50]

def make_image_filename(prompt, index=0):
    num = str(index).zfill(3)
    words = re.sub(r'[^a-zA-Z0-9\s]', '', prompt).split()
    slug = '-'.join(words[:4]).lower()
    return f"{num}-{slug}-By_@TurabCoder.png"

def now_iso():
    return datetime.now(timezone.utc).isoformat()
