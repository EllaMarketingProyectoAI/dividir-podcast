import os
import requests
import subprocess
import math
from moviepy.editor import VideoFileClip
import time

class TimeoutError(Exception):
    pass

def descargar_con_progreso(url_video, local_filename, timeout=300):
    try:
        print(f"Descargando video desde: {url_video}")
        start_time = time.time()
        response = requests.get(url_video, stream=True, timeout=30)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))
        downloaded = 0
        with open(local_filename, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded % (10 * 1024 * 1024) == 0 and total_size > 0:
                        progress = (downloaded / total_size) * 100
                        print(f"Descargado: {progress:.1f}% ({downloaded / (1024*1024):.1f}MB)")
                    if time.time() - start_time > timeout:
                        raise TimeoutError("Timeout en descarga")
        print(f"Descarga completada en {time.time() - start_time:.2f} segundos")
    except Exception as e:
        print(f"Error en descarga: {str(e)}")
        if os.path.exists(local_filename):
            os.remove(local_filename)
        raise

def ejecutar_ffmpeg_con_timeout(comando, timeout=600):
    try:
        print(f"Ejecutando: {' '.join(comando)}")
        start_time = time.time()
        process = subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, comando, stderr)
            print(f"FFmpeg completado en {time.time() - start_time:.2f} segundos")
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise TimeoutError(f"FFmpeg timeout después de {timeout} segundos")
    except Exception as e:
        print(f"Error en FFmpeg: {str(e)}")
        raise

def dividir_video(url_video, base_name, session_id):
    tmp_folder = "/tmp"
    local_filename = os.path.join(tmp_folder, f"{session_id}.mp4")
    descargar_con_progreso(url_video, local_filename, timeout=600)
    if not os.path.exists(local_filename):
        raise Exception("El archivo no se descargó correctamente")

    try:
        video = VideoFileClip(local_filename)
        duracion = math.floor(video.duration)
        print(f"Duración del video: {duracion} segundos")
    finally:
        video.close()

    partes = duracion // 600 + int(duracion % 600 > 0)
    resultados = []

    for i in range(partes):
        start = i * 600
        clip_duration = min(600, duracion - start)
        output_name = f"{base_name}_clip{i+1}.mp4"
        output_mp4 = os.path.join(tmp_folder, output_name)
        output_mp3 = output_mp4.replace(".mp4", ".mp3")

        comando_mp4 = [
            "ffmpeg", "-y", "-ss", str(start), "-i", local_filename,
            "-t", str(clip_duration), "-c:v", "libx264", "-preset", "ultrafast",
            "-crf", "28", "-c:a", "aac", "-avoid_negative_ts", "make_zero",
            "-fflags", "+genpts", output_mp4
        ]
        ejecutar_ffmpeg_con_timeout(comando_mp4, timeout=900)

        comando_mp3 = [
            "ffmpeg", "-y", "-i", output_mp4,
            "-q:a", "2", "-map", "a", output_mp3
        ]
        ejecutar_ffmpeg_con_timeout(comando_mp3, timeout=300)

        resultados.append({
            "n": i + 1,
            "nombre": output_name,
            "ruta_mp4": output_mp4,
            "ruta_mp3": output_mp3,
            "duracion": clip_duration
        })

    os.remove(local_filename)
    return resultados

def limpiar_archivos_temporales(clips_info):
    for clip in clips_info:
        try:
            if os.path.exists(clip['ruta_mp4']):
                os.remove(clip['ruta_mp4'])
            if os.path.exists(clip['ruta_mp3']):
                os.remove(clip['ruta_mp3'])
        except Exception as e:
            print(f"Error limpiando {clip['nombre']}: {str(e)}")
    print("Archivos temporales limpiados")
