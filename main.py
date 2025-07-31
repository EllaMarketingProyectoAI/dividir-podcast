from flask import Flask, request, jsonify
import os, uuid, tempfile, requests
from moviepy.editor import VideoFileClip
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME", "videospodcast")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
app = Flask(__name__)

@app.route("/", methods=["POST"])
def dividir_podcast():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        video_url = data.get("url_video")
        supabase_file_name = data.get("supabaseFileName")

        if not user_id or not video_url or not supabase_file_name:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        print(f"✅ Iniciando procesamiento para: {video_url}")

        # Descargar el video a archivo temporal
        response = requests.get(video_url, stream=True, timeout=30)
        response.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            for chunk in response.iter_content(chunk_size=8192):
                tmp.write(chunk)
            temp_video_path = tmp.name

        print("🎬 Cargando video con MoviePy...")
        video = VideoFileClip(temp_video_path)

        # Dividir en bloques de 10 minutos
        segment_duration = 600
        duration = video.duration
        output_dir = tempfile.mkdtemp()
        urls_clips = []

        print(f"🕒 Duración total: {duration} segundos")

        for i, start in enumerate(range(0, int(duration), segment_duration)):
            end = min(start + segment_duration, duration)
            clip = video.subclip(start, end)
            output_filename = f"{uuid.uuid4()}_clip_{i+1}.mp4"
            output_path = os.path.join(output_dir, output_filename)

            print(f"✂️ Escribiendo clip {i+1}: {start}-{end} s")
            clip.write_videofile(
                output_path,
                codec="libx264",
                audio_codec="aac",
                threads=1,
                preset="ultrafast"
            )

            with open(output_path, "rb") as f:
                supabase.storage.from_(BUCKET_NAME).upload(
                    f"clips/{user_id}/{output_filename}",
                    f,
                    {"content-type": "video/mp4"},
                    upsert=True
                )

            public_url = f"{SUPABASE_URL}/storage/v1/object/public/{BUCKET_NAME}/clips/{user_id}/{output_filename}"
            urls_clips.append(public_url)
            print(f"📤 Clip {i+1} subido: {public_url}")

        return jsonify({"status": "success", "clips": urls_clips}), 200

    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
