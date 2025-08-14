from flask import Flask, request, jsonify, g
import os, uuid, subprocess, requests, shutil, sys, time, json, logging

# === CONFIG ===
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE = os.getenv("SUPABASE_SERVICE_ROLE", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "videogeneral")
SUPABASE_DEST_PREFIX = os.getenv("SUPABASE_DEST_PREFIX", "VideosFinales/")
PRIVATE_BUCKET = os.getenv("PRIVATE_BUCKET", "false").lower() == "true"

PORT = int(os.getenv("PORT", "8080"))
TMP_DIR = "/tmp"

# === Logging básico ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("merge-app")

app = Flask(__name__)

# === Hooks de request/response ===
@app.before_request
def start_timer_and_request_id():
    g.start = time.time()
    rid = request.headers.get("X-Request-Id") or request.args.get("requestId")
    g.request_id = rid or uuid.uuid4().hex[:8]
    log.info(f"[{g.request_id}] {request.method} {request.path} ua={request.headers.get('User-Agent')}")

@app.after_request
def add_request_id_to_response(resp):
    rid = getattr(g, "request_id", None)
    if rid:
        resp.headers["X-Request-Id"] = rid
    dt = time.time() - getattr(g, "start", time.time())
    log.info(f"[{rid}] {request.method} {request.path} -> {resp.status_code} in {dt*1000:.1f}ms")
    return resp

# === Manejadores de error ===
@app.errorhandler(400)
def bad_request(e):
    rid = getattr(g, "request_id", "-")
    log.warning(f"[{rid}] 400 {e}")
    return jsonify({"ok": False, "error": "bad_request", "detail": str(e)}), 400

@app.errorhandler(500)
def internal_error(e):
    rid = getattr(g, "request_id", "-")
    log.error(f"[{rid}] 500 {e}", exc_info=True)
    return jsonify({"ok": False, "error": "internal", "detail": "Internal Server Error"}), 500

# === Utilidades ===
UA = "Mozilla/5.0 (X11; Linux x86_64) EllaMerge/1.0"

def _looks_like_mp4(buf: bytes) -> bool:
    return b"ftyp" in (buf[:4096] if buf else b"")

def _get(url, timeout=300):
    return requests.get(url, stream=True, timeout=timeout, headers={"User-Agent": UA})

def download_to_tmp(url: str, dst_path: str, timeout=300):
    r = _get(url, timeout=timeout)
    r.raise_for_status()

    ctype = r.headers.get("Content-Type", "")
    if not (ctype.startswith("video/") or ctype.startswith("application/octet-stream")):
        # Fallback para Supabase: forzar ?download=1
        if "supabase.co" in url and "storage/v1/object/" in url and "download=" not in url:
            url2 = url + ("&download=1" if "?" in url else "?download=1")
            r2 = _get(url2, timeout=timeout)
            r2.raise_for_status()
            ctype2 = r2.headers.get("Content-Type", "")
            if ctype2.startswith("video/") or ctype2.startswith("application/octet-stream"):
                r = r2
                ctype = ctype2
            else:
                sample = r2.raw.read(256, decode_content=True)
                raise ValueError(f"URL no devuelve video (fallback). Content-Type={ctype2}. Sample={sample[:80]!r}")
        else:
            sample = r.raw.read(256, decode_content=True)
            raise ValueError(f"URL no devuelve video. Content-Type={ctype}. Sample={sample[:80]!r}")

    total = 0
    first = b""
    with open(dst_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024*512):
            if not chunk:
                continue
            if total == 0:
                first = chunk[:4096]
            f.write(chunk)
            total += len(chunk)

    if total < 1024:
        raise ValueError(f"Archivo descargado muy pequeño ({total} bytes).")
    if not _looks_like_mp4(first):
        log.warning(f"El archivo no muestra 'ftyp' en cabecera: {dst_path}")

def run_ffmpeg(args, timeout=1800):
    proc = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.decode("utf-8", errors="ignore"))
    return proc

def supabase_upload(local_path: str, dest_path: str, content_type="video/mp4", upsert=True):
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
        sign_url = f"{SUPABASE_URL}/storage/v1/object/sign/{key}"
        body = {"expiresIn": 86400}
        sresp = requests.post(sign_url, headers={
            "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE}",
            "apikey": SUPABASE_SERVICE_ROLE,
            "Content-Type": "application/json",
        }, data=json.dumps(body))
        if sresp.status_code >= 400:
            raise RuntimeError(f"Sign failed: {sresp.status_code} {sresp.text}")
        signed = sresp.json().get("signedURL")
        return {"key": key, "signedUrl": f"{SUPABASE_URL}{signed}"}
    else:
        public_url = f"{SUPABASE_URL}/storage/v1/object/public/{key}"
        return {"key": key, "publicUrl": public_url}

# === Rutas ===
@app.get("/health")
def health():
    return jsonify({"ok": True})

@app.post("/concat")
def concat():
    log.info(f"ENV check: URL set={bool(SUPABASE_URL)}, SR set={bool(SUPABASE_SERVICE_ROLE)}")
    try:
        data = request.get_json(force=True, silent=False)
        if not data or "clips" not in data or not isinstance(data["clips"], list) or len(data["clips"]) < 1:
            return jsonify({"ok": False, "detail": "clips (array) requerido"}), 400

        clips = data["clips"]
        for i, u in enumerate(clips):
            if not isinstance(u, str) or not u.startswith("http"):
                return jsonify({"ok": False, "detail": f"URL inválida en clips[{i}]: {u}"}), 400

        output_name = (data.get("output") or f"final_{uuid.uuid4().hex[:8]}.mp4").strip()
        reencode = bool(data.get("reencode", True))
        dest_prefix = data.get("destPrefix") or SUPABASE_DEST_PREFIX
        upload_flag = bool(data.get("upload", True))

        work_id = uuid.uuid4().hex[:8]
        work_dir = os.path.join(TMP_DIR, f"merge_{work_id}")
        os.makedirs(work_dir, exist_ok=True)

        log.info(f"[{g.request_id}] Descargando {len(clips)} clips...")
        local_files = []
        for i, url in enumerate(clips, start=1):
            log.info(f"[{g.request_id}] clip[{i}] GET {url}")
            dst = os.path.join(work_dir, f"part_{i:02d}.mp4")
            download_to_tmp(url, dst, timeout=600)
            log.info(f"[{g.request_id}] clip[{i}] ok -> {dst} ({os.path.getsize(dst)} bytes)")
            local_files.append(dst)

        list_path = os.path.join(work_dir, "inputs.txt")
        with open(list_path, "w") as f:
            for p in local_files:
                f.write(f"file '{p}'\n")

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
            args = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", list_path, "-c", "copy", output_path]

        log.info(f"[{g.request_id}] Ejecutando FFmpeg reencode={reencode}")
        run_ffmpeg(args, timeout=3600)

        result = {"ok": True, "work_id": work_id, "output_name": output_name}
        if upload_flag:
            dest_path = f"{dest_prefix}{output_name}".lstrip("/")
            up = supabase_upload(output_path, dest_path, content_type="video/mp4", upsert=True)
            result.update(up)

        return jsonify(result)

    except ValueError as e:
        log.warning(f"[{g.request_id}] 400 {e}")
        return jsonify({"ok": False, "detail": str(e)}), 400
    except requests.HTTPError as e:
        log.warning(f"[{g.request_id}] 502 download failed: {e}")
        return jsonify({"ok": False, "detail": f"Download failed: {str(e)}"}), 502
    except subprocess.TimeoutExpired:
        log.error(f"[{g.request_id}] 504 FFmpeg timeout")
        return jsonify({"ok": False, "detail": "FFmpeg timeout"}), 504
    except RuntimeError as e:
        log.error(f"[{g.request_id}] 500 runtime: {e}")
        return jsonify({"ok": False, "detail": f"FFmpeg/Supabase error: {str(e)[:2000]}"}), 500
    except Exception as e:
        log.error(f"[{g.request_id}] 500 unexpected: {e}", exc_info=True)
        return jsonify({"ok": False, "detail": f"Internal error: {str(e)}"}), 500
    finally:
        shutil.rmtree(locals().get("work_dir", "/tmp/none"), ignore_errors=True)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=PORT)
