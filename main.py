from flask import Flask, request, jsonify
from utils.ffmpeg_split import split_video_into_clips
from utils.supabase_upload import upload_clip_to_supabase
import os
import requests
import uuid

app = Flask(__name__)

@app.route("/procesar", methods=["POST"])
def procesar():
    data = request.json

    if data is None:
        return jsonify({"error": "Request must contain JSON data"}), 400

    url_video = data.get("url_video")
    user_id = data.get("user_id")

    if not url_video or not user_id:
        return jsonify({"error": "Faltan datos"}), 400

    # Ejecutar función de división de video
    output_urls = split_video_into_clips(url_video, user_id)

    return jsonify({
        "message": "Procesamiento exitoso",
        "urls": output_urls
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=3000)