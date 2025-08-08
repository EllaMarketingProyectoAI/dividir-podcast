from flask import Flask, request, jsonify
import os
import uuid
from dividir_video import dividir_video, limpiar_archivos_temporales
from supabase_upload import upload_to_supabase

app = Flask(__name__)

@app.route("/", methods=["GET"])
def healthcheck():
    return "✅ Service running", 200

@app.route("/split", methods=["POST"])
def split_video():
    try:
        data = request.get_json()
        video_url = data.get("url_video")
        user_id = data.get("user_id")
        supabase_filename = data.get("supabaseFileName")

        if not video_url or not supabase_filename or not user_id:
            return jsonify({"error": "Faltan campos requeridos"}), 400

        session_id = uuid.uuid4().hex
        resultados = dividir_video(video_url, supabase_filename, session_id)

        rutas_mp4 = [r["ruta_mp4"] for r in resultados]
        rutas_mp3 = [r["ruta_mp3"] for r in resultados]

        urls_mp4 = upload_to_supabase(rutas_mp4, "videospodcast/PodcastCortados", "video/mp4")
        urls_mp3 = upload_to_supabase(rutas_mp3, "videospodcast/PodcastCortadosAudio", "audio/mpeg")

        limpiar_archivos_temporales(resultados)

        return jsonify({
            "video_urls": urls_mp4,
            "audio_urls": urls_mp3,
            "total_clips": len(urls_mp4)
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port = "5000")
