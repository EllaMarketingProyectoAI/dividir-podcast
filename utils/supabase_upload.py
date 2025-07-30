import os
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# Ensure that environment variables are not None
if SUPABASE_URL is None or SUPABASE_KEY is None:
    raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def upload_clip_to_supabase(filepath, user_id, video_id):
    nombre = os.path.basename(filepath)

    ruta_final = f"ClipsPodcast/{user_id}/{video_id}/{nombre}"

    with open(filepath, "rb") as f:
        supabase.storage.from_("videospodcast").upload(ruta_final, f)

    print(f"✅ Subido: {ruta_final}")

