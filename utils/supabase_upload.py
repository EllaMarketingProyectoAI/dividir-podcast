import os
from supabase import create_client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET = "videospodcast"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_to_supabase(file_paths, folder, mime_type):
    urls = []
    for path in file_paths:
        file_name = os.path.basename(path)
        storage_path = f"{folder}/{file_name}"
        with open(path, "rb") as f:
            supabase.storage.from_(BUCKET).upload(
                storage_path, f,
                {"content-type": mime_type, "x-upsert": "true"}
            )
            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET}/{storage_path}"
            urls.append(public_url)
    return urls
