import os
import json
import requests
import subprocess
from flask import Flask, request, jsonify
from utils.supabase_upload import upload_clip_to_supabase

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
BUCKET_NAME = "videospodcast"

app = Flask(__name__)

@app.route("/", methods=["POST"])
def dividir_video():
    try:
        data = request.get_json(force = True)
        
         user_id = data.get("userId")
        video_url = data.get("video_url")
        supabase_file_name = data.get("supabaseFileName")
      
        input_filename = "input_video.mp4"
        output_folder = "clipped"
        os.makedirs(output_folder, exist_ok=True)

        # Descargar video original
        with open(input_filename, "wb") as f:
            response = requests.get(video_url)
            f.write(response.content)

        # Calcular duración total con FFmpeg
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", input_filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        duration = float(result.stdout.strip())
        total_parts = int(duration // 600) + (1 if duration % 600 > 0 else 0)

        output_files = []
        for i in range(total_parts):
            start_time = i * 600
            output_filename = f"{output_folder}/part_{i+1}.mp4"

            subprocess.run([
                "ffmpeg", "-i", input_filename,
                "-ss", str(start_time), "-t", "600",
                "-c:v", "libx264", "-c:a", "aac",
                "-strict", "experimental", output_filename
            ], check=True)

            # Generar nombre dinámico final
            supabase_path = f"PodcastCortados/{userId}_{supabaseFileName}_parte{i+1}.mp4"
            upload_clip_to_supabase(output_filename, BUCKET_NAME, supabase_path)

            output_files.append({
                "parte": i+1,
                "supabase_path": f"{BUCKET_NAME}/{supabase_path}"
            })

        return jsonify({"message": "Video dividido y subido correctamente", "clips": output_files})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)
