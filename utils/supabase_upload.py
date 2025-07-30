import os
from supabase import create_client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

def upload_clip_to_supabase(local_path, bucket_name, supabase_path):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    with open(local_path, "rb") as f:
        data = f.read()

    supabase.storage.from_(bucket_name).upload(supabase_path, data, {
        "content-type": "video/mp4",
        "x-upsert": "true"
    })
