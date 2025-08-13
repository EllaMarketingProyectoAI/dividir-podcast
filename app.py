from flask import Flask, request, jsonify
import os, uuid, subprocess, requests, shutil, json

# ==== Config ====
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "videogeneral")
# Carpeta destino en el bucket para guardar el video final
SUPABASE_DEST_PREFIX = os.getenv("SUPABASE_DEST_PREFIX", "VideosFinales/")
# Si tu bucket es privado y quieres URL firmada
PRIVATE_BUCKET = os.getenv("PRIVATE_BUCKET", "false").lower() == "true"

PORT = int(os.getenv("PORT", "8080"))
TMP_DIR = "/tmp"

app = Flask(__name__)


# ==== Utils ====
def safe_name(name: str) -> str:
    return "".join(c for c in name if c.isalnum() or c in "-_.").strip() or "file"

def download_to_tmp(url: str, dst_path: str, timeout=300):
    with requests.get(url, stream=True, timeout=timeout) as r:
        r.raise_for_status()
        with open(dst_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 512):
                if chunk:
                    f.write(chunk)

def run_ffmpeg(args, timeout=1800):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore"))
    return proc

def supabase_upload(local_path: str, dest_path: str, content_type="video/mp4", upsert=True):
    """
    Sube un archivo a Supabase Storage usando el endpoint HTTP.
    Devuelve dict con { "key": "<bucket>/<path>", "publicUrl"/"signedUrl": "<url>" }
    """
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE:
        raise RuntimeError("Faltan SUPABASE_URL o SUPABASE_SERVICE_ROLE")

    url = f"{SUPABASE_URL}/storage/v1/object/{SUPABASE_BUCKET}/{dest_path}"
    headers = {
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
        "apikey": SUPABASE_SERVICE_ROLE,
        "Content-Type": content_type,
    }
    if upsert:
        headers["x-upsert"] = "true"

    with open(local_path, "rb") as f:
        resp = requests.post(url, headers=headers, data=f)
    if resp.status_code >= 400:
        raise RuntimeError(f"Upload failed: {resp.status_code} {resp.text}")

    key = f"{SUPABASE_BUCKET}/{dest_path}"

    if PRIVATE_BUCKET:
        # Crear signed URL
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{key}"
        body = {"expiresIn": 86400}  # 24h
        sresp = requests.post(sign_url, headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
            "apikey": SUPABASE_SERVICE_ROLE,
            "Content-Type": "application/json",
        }, data=json.dumps(body))
        if sresp.status_code >= 400:
            raise RuntimeError(f"Sign failed: {sresp.status_code} {sresp.text}")
        signed = sresp.json().get("signedURL")
        return {
            "key": key,
            "signedUrl": f"{SUPABASE_URL}{signed}",
        }
    else:
        # URL pública directa
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{key}"
        return {"key": key, "publicUrl": public_url}


# ==== Routes ====
@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/concat")
def concat():
    """
    Payload esperado (JSON):
    {
      "clips": ["https://.../clip_01.mp4", "https://.../clip_02.mp4"],
      "output": "final_video.mp4",     // opcional, default: final_<8char>.mp4
      "reencode": true,                // opcional, default: true
      "destPrefix": "VideosFinales/",  // opcional, sobreescribe SUPABASE_DEST_PREFIX
      "upload": true                   // opcional, default: true (sube a supabase)
    }
    Respuesta:
    - ok: True/False
    - work_id, output_name
    - publicUrl/signedUrl (si upload=true)
    - detail (errores)
    """
    try:
        data = request.get_json(force=True, silent=False)
        if not data or "clips" not in data or not isinstance(data["clips"], list) or len(data["clips"]) < 1:
            return jsonify({"ok": False, "detail": "clips (array) requerido"}), 400

        clips = data["clips"]
        # Validar URLs
        for i, u in enumerate(clips):
            if not isinstance(u, str) or not u.startswith("http"):
                return jsonify({"ok": False, "detail": f"URL inválida en clips[{i}]: {u}"}), 400

        output_name = safe_name(data.get("output", f"final_{uuid.uuid4().hex[:8]}.mp4"))
        reencode = bool(data.get("reencode", True))
        dest_prefix = data.get("destPrefix") or SUPABASE_DEST_PREFIX
        upload_flag = bool(data.get("upload", True))

        # Carpeta de trabajo
        work_id = uuid.uuid4().hex[:8]
        work_dir = os.path.join(TMP_DIR, f"merge_{work_id}")
        os.makedirs(work_dir, exist_ok=True)

        # Descargar clips
        local_files = []
        for i, url in enumerate(clips, start=1):
            dst = os.path.join(work_dir, f"part_{i:02d}.mp4")
            download_to_tmp(url, dst, timeout=600)
            local_files.append(dst)

        # Archivo lista para concat demuxer
        list_path = os.path.join(work_dir, "inputs.txt")
        with open(list_path, "w") as f:
            for p in local_files:
                f.write(f"file '{p}'\n")

        # Ejecutar ffmpeg
        output_path = os.path.join(work_dir, output_name)
        if reencode:
            args = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_path,
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                "-c:a", "aac", "-b:a", "160k",
                output_path
            ]
        else:
            args = [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", list_path, "-c", "copy", output_path
            ]
        run_ffmpeg(args, timeout=3600)

        result = {
            "ok": True,
            "work_id": work_id,
            "output_name": output_name,
        }

        if upload_flag:
            # Destino en bucket (ej. VideosFinales/final_XXXX.mp4)
            dest_path = f"{dest_prefix}{output_name}".lstrip("/")
            up = supabase_upload(output_path, dest_path, content_type="video/mp4", upsert=True)
            result.update(up)

        return jsonify(result)

    except requests.HTTPError as e:
        return jsonify({"ok": False, "detail": f"Download failed: {str(e)}"}), 502
    except subprocess.TimeoutExpired:
        return jsonify({"ok": False, "detail": "FFmpeg timeout"}), 504
    except RuntimeError as e:
        return jsonify({"ok": False, "detail": f"FFmpeg/Supabase error: {str(e)[:2000]}"}), 500
    except Exception as e:
        return jsonify({"ok": False, "detail": f"Internal error: {str(e)}"}), 500
    finally:
        # Limpieza opcional (comenta si quieres inspeccionar /tmp)
        shutil.rmtree(locals().get("work_dir", "/tmp/none"), ignore_errors=True)


if __name__ == "__main__":
    # Para debug local; en Railway usaremos gunicorn
    app.run(host="0.0.0.0", port=PORT)
