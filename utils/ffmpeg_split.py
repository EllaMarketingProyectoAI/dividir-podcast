import subprocess
import os

def split_video_into_clips(video_path, duracion_segmento=600):  # 600 seg = 10 min
    nombre_base = os.path.splitext(os.path.basename(video_path))[0]
    output_dir = "clips"
    os.makedirs(output_dir, exist_ok=True)

    comando = [
        "ffmpeg",
        "-i", video_path,
        "-c", "copy",
        "-map", "0",
        "-segment_time", str(duracion_segmento),
        "-f", "segment",
        f"{output_dir}/{nombre_base}_%03d.mp4"
    ]

    subprocess.run(comando, check=True)

    # Regresar lista de rutas
    return [f"{output_dir}/{nombre_base}_{i:03d}.mp4" for i in range(100) if os.path.exists(f"{output_dir}/{nombre_base}_{i:03d}.mp4")]
