import json
import threading
import ffmpeg

from app.core.config import (
    BG_VIDEO, LOGO, INPUT, OUTPUT,
    DURATION, WIDTH, HEIGHT, FPS
)
from app.core.state import estado
from app.services.pauta_service import get_valid_rows

def start_generation():
    if estado["running"]:
        return False
    threading.Thread(target=run_make_clips, daemon=True).start()
    return True

def run_make_clips():
    estado.update({
        "running": True,
        "log": [],
        "done": 0,
        "errors": 0,
        "total": 0
    })

    pauta = get_valid_rows()

    if not pauta:
        estado["log"].append("✗ La pauta está vacía o incompleta")
        estado["running"] = False
        return

    estado["total"] = len(pauta)
    estado["log"].append(f"ℹ Procesando {len(pauta)} clips...")

    for row in pauta:
        procesar_clip(row)

    estado["running"] = False

def procesar_clip(row):
    numero = row["numero"].zfill(2)
    nombre = row["nombre"].upper()
    foto_path = INPUT / row["foto"]
    salida = OUTPUT / f"{numero} {nombre}.mp4"

    estado["log"].append(f"→ [{numero}] {nombre}...")

    if not foto_path.exists():
        estado["log"].append(f'✗ Foto no encontrada: {row["foto"]}')
        estado["errors"] += 1
        return

    try:
        bg = (
            ffmpeg
            .input(str(BG_VIDEO), stream_loop=-1, t=DURATION)
            .filter("scale", WIDTH, HEIGHT, force_original_aspect_ratio="increase")
            .filter("crop", WIDTH, HEIGHT)
            .filter("setpts", "PTS-STARTPTS")
        )

        foto = (
            ffmpeg
            .input(str(foto_path), loop=1, t=DURATION)
            .filter("scale", 8000, -1)
            .filter(
                "zoompan",
                z="zoom+0.001",
                x="iw/2-(iw/zoom/2)",
                y="ih/2-(ih/zoom/2)",
                d=DURATION * FPS,
                s=f"{WIDTH}x{HEIGHT}",
                fps=FPS
            )
            .filter("setpts", "PTS-STARTPTS")
        )

        logo = (
            ffmpeg
            .input(str(LOGO), loop=1, t=DURATION)
            .filter("setpts", "PTS-STARTPTS")
        )

        comp = ffmpeg.overlay(bg, foto)
        comp = ffmpeg.overlay(comp, logo)

        try:
            audio = ffmpeg.input(str(BG_VIDEO), t=DURATION).audio
            (
                ffmpeg
                .output(
                    comp, audio, str(salida),
                    vcodec="libx264",
                    acodec="aac",
                    pix_fmt="yuv420p",
                    r=FPS,
                    t=DURATION,
                    **{"b:v": "8M", "preset": "fast", "crf": "18"}
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error:
            (
                ffmpeg
                .output(
                    comp, str(salida),
                    vcodec="libx264",
                    pix_fmt="yuv420p",
                    r=FPS,
                    t=DURATION,
                    **{"b:v": "8M", "preset": "fast", "crf": "18"}
                )
                .overwrite_output()
                .run(quiet=True)
            )

        estado["done"] += 1
        estado["log"].append(f"✓ {numero} {nombre}.mp4")

    except Exception as e:
        estado["errors"] += 1
        estado["log"].append(f"✗ Error en {nombre}: {str(e)[:80]}")