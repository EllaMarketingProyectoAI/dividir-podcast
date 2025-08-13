# FFmpeg Merge Service (Railway + Supabase)

Servicio Flask para **concatenar videos** con FFmpeg y **subir resultado a Supabase Storage**.

## Endpoints

- `GET /health` → `{ "ok": true }`
- `POST /concat`  
  **Body (JSON):**
  ```json
  {
    "clips": ["https://.../clip_01.mp4", "https://.../clip_02.mp4"],
    "output": "final_video.mp4",
    "reencode": true,
    "destPrefix": "VideosFinales/",
    "upload": true
  }


# FFmpeg Merge Service (Railway + Supabase)

Servicio Flask para concatenar videos con FFmpeg y subir el resultado a Supabase Storage.

## Variables de entorno

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE`
- `SUPABASE_BUCKET` (default: videogeneral)
- `SUPABASE_DEST_PREFIX` (default: VideosFinales/)
- `PRIVATE_BUCKET` ("true" o "false")
- `PORT` (default: 8080)

## Endpoints

### `GET /health`
Devuelve `{"ok": true}` si el servicio está vivo.

### `POST /concat`
Body (JSON):
```json
{
  "clips": ["<url1>", "<url2>"],
  "output": "final_video.mp4",
  "reencode": true,
  "upload": true,
  "destPrefix": "VideosFinales/"
}
