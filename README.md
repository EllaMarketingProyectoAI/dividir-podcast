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
