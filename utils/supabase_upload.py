import os
from supabase import create_client

def upload_clip_to_supabase(binary_data, original_url, user_id, index):
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")
    bucket = os.environ.get("BUCKET_NAME", "videospodcast")

    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")

    # Obtener nombre base del archivo original sin extensión
    original_filename = original_url.split("/")[-1].split(".mp4")[0]
    
    # Crear nuevo nombre con sufijo "_parteX"
    new_filename = f"{original_filename}_parte{index}.mp4"
    
    # Ruta destino final dentro del bucket
    storage_path = f"PodcastCortados/{user_id}/{new_filename}"

    # Inicializar cliente Supabase
    supabase = create_client(supabase_url, supabase_key)

    # Subir el archivo binario
    supabase.storage.from_(bucket).upload(storage_path, binary_data, file_options={"content-type": "video/mp4"})

    # Construir URL pública
    public_url = f"{supabase_url}/storage/v1/object/public/{bucket}/{storage_path}"
    return public_url
