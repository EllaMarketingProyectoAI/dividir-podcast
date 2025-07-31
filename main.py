from flask import Flask, request, jsonify
import requests
import os
import uuid
from moviepy.editor import VideoFileClip
from supabase import create_client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BUCKET_NAME = os.getenv("BUCKET_NAME")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

app = Flask(__name__)

@app.route("/", methods=["POST"])
def dividir_podcast():
    try:
        data = request.get_json(force=True)
        user_id = data.get("user_id")
        video_url = data.get("url_video")
        supabase_file_name = data.get("supabaseFileName")

        if not user_id or not url_video or not supabase_file_name:
            return jsonify({"status": "error", "message": "Missing required fields"}), 400

        print(f"🎥 URL: {url_video}")
        print(f"👤 User ID: {user_id}")
        print(f"🗂️ Archivo: {supabase_file_name}")

        # Crear carpeta temporal
        os.makedirs("temp", exist_ok=True)
        video_path = os.path.join("temp", supabase_file_name)

        # Descargar video
        response = requests.get(url_video)
        with open(video_path, "wb") as f:
            f.write(response.content)

        # Dividir video
        clip = VideoFileClip(video_path)
        duration = int(clip.duration)
        segment_duration = 600  # 10 minutos = 600 segundos

        folder_output = "temp/output"
        os.makedirs(folder_output, exist_ok=True)

        clip_urls = []

        for i in range(0, duration, segment_duration):
            subclip = clip.subclip(i, min(i + segment_duration, duration))
            output_filename = f"{user_id}_clip_{i//segment_duration + 1}.mp4"
            output_path = os.path.join(folder_output, output_filename)

            subclip.write_videofile(output_path, codec="libx264", audio_codec="aac")

            # Subir a Supabase en la carpeta PodcastCortados
            with open(output_path, "rb") as video_file:
                supabase.storage.from_("ellaproyecto").upload(
                    file=video_file,
                    path=f"videospodcast/PodcastCortados/{output_filename}",
                    file_options={"content-type": "video/mp4"},
                    upsert=True
                )

            public_url = f"{SUPABASE_URL}/storage/v1/object/public/ellaproyecto/videospodcast/PodcastCortados/{output_filename}"
            clip_urls.append(public_url)

        # Limpieza
        clip.close()

        return jsonify({
            "status": "success",
            "total_clips": len(clip_urls),
            "clips": clip_urls
        })

    except Exception as e:
        print(f"❌ Error interno: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host="0.0.0.0", port=port)
