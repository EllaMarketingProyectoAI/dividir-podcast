from flask import Flask, request, jsonify
import os
import requests
import uuid
import tempfile
from moviepy.editor import VideoFileClip
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "videospodcast")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

@app.route("/", methods=["POST"])
def dividir_podcast():
    try:
        # Obtener campos del JSON
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        video_url = data.get("url_video")
        supabase_file_name = data.get("supabaseFileName")

        # Validación de campos
        if not user_id or not video_url or not supabase_file_name:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        print(f"📥 Recibiendo video: {video_url}")

        # Descargar el video en archivo temporal
        response = requests.get(video_url, stream=True)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    tmp.write(chunk)
            temp_video_path = tmp.name

        print(f"✅ Video descargado en {temp_video_path}")

        # Cargar el video con moviepy
        video = VideoFileClip(temp_video_path)
        duration = video.duration
        segment_duration = 600  # 10 minutos = 600 segundos

        urls_clips = []
        output_dir = tempfile.mkdtemp()

        # Cortar en segmentos
        for i, start in enumerate(range(0, int(duration), segment_duration)):
            end = min(start + segment_duration, duration)
            clip = video.subclip(start, end)
            clip_filename = f"{uuid.uuid4()}_clip_{i+1}.mp4"
            clip_path = os.path.join(output_dir, clip_filename)
            clip.write_videofile(clip_path, codec="libx264", audio_codec="aac")

            # Subir a Supabase
            with open(clip_path, "rb") as f:
                supabase.storage.from_(BUCKET_NAME).upload(
                    path=f"clips/{user_id}/{clip_filename}",
                    file=f,
                    file_options={"content-type": "video/mp4"},
                    upsert=True
                )

            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/clips/{user_id}/{clip_filename}"
            urls_clips.append(public_url)
            print(f"📤 Clip {i+1} subido: {public_url}")

        return jsonify({"status": "success", "clips": urls_clips}), 200

    except Exception as e:
        print("❌ Error:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
