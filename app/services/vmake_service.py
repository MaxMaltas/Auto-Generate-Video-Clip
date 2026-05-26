"""
vmake_service.py
────────────────
Servicio de eliminación de grafismos en vídeo via Vmake API (videoscreenclear).

Flujo completo:
  1. Editor sube vídeo → guardado en temp/vmake/input/
  2. POST /vmake/procesar → lanza thread worker
  3. Worker: SkillClient.run_task("videoscreenclear", path) → upload OSS + consume + invoke + poll
  4. Resultado descargado a temp/vmake/output/
  5. Editor previsualiza y descarga desde /vmake/resultado/<nombre>

Estado compartido sigue el mismo patrón que clip_service.py y titular_premiere_service.py.
"""

import os
import threading
import time
import traceback
from pathlib import Path

import requests as _requests

from app.core.config import TEMP

# ── Directorios ───────────────────────────────────────────────────────────────

VMAKE_INPUT  = TEMP / "vmake" / "input"
VMAKE_OUTPUT = TEMP / "vmake" / "output"

VMAKE_INPUT.mkdir(parents=True, exist_ok=True)
VMAKE_OUTPUT.mkdir(parents=True, exist_ok=True)

# ── Formatos de vídeo permitidos ──────────────────────────────────────────────

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".m4v", ".3gp"}

# ── Estado compartido ─────────────────────────────────────────────────────────

_estado: dict = {
    "running":   False,
    "log":       [],
    "done":      0,
    "errors":    0,
    "total":     1,
    "resultado": None,
}
_lock = threading.Lock()


def get_estado() -> dict:
    return dict(_estado)


# ── Entrada pública ───────────────────────────────────────────────────────────

def iniciar_procesado(filename: str) -> bool:
    with _lock:
        if _estado["running"]:
            return False
        _estado.update({
            "running":   True,
            "log":       [],
            "done":      0,
            "errors":    0,
            "total":     1,
            "resultado": None,
        })

    threading.Thread(target=_run_procesado, args=(filename,), daemon=True).start()
    return True


# ── Worker ────────────────────────────────────────────────────────────────────

def _log(msg: str) -> None:
    _estado["log"].append(msg)


def _run_procesado(filename: str) -> None:
    try:
        _procesar(filename)
    except Exception as exc:
        _estado["errors"] = 1
        _log(f"ERR Error inesperado: {str(exc)[:300]}")
        _log(f"ERR Traceback: {traceback.format_exc()[-400:]}")
    finally:
        _estado["running"] = False


def _procesar(filename: str) -> None:
    video_path = VMAKE_INPUT / filename
    if not video_path.exists():
        _estado["errors"] = 1
        _log(f"ERR Archivo no encontrado: {filename}")
        return

    ak = os.environ.get("MT_AK", "").strip()
    sk = os.environ.get("MT_SK", "").strip()
    if not ak or not sk:
        _estado["errors"] = 1
        _log("ERR Credenciales Vmake no configuradas (MT_AK / MT_SK)")
        return

    _log(f"→ Archivo: {filename}")
    _log("→ Conectando con Vmake API...")

    try:
        from sdk import SkillClient
    except ImportError as e:
        _estado["errors"] = 1
        _log(f"ERR SDK no disponible: {e}")
        return

    try:
        client = SkillClient(ak=ak, sk=sk)
    except Exception as e:
        _estado["errors"] = 1
        _log(f"ERR Error inicializando cliente: {str(e)[:200]}")
        return

    _log("→ Subiendo vídeo a Vmake (puede tardar según el tamaño)...")

    try:
        result = client.run_task(
            task_name="videoscreenclear",
            image_path=str(video_path),
            params={"parameter": {"rsp_media_type": "url"}},
        )
    except Exception as e:
        _estado["errors"] = 1
        _log(f"ERR Error durante el procesado: {str(e)[:300]}")
        return

    # ── Logging completo del resultado para diagnóstico ───────────────────────
    _log(f"→ Respuesta Vmake: skill_status={result.get('skill_status')!r} "
         f"output_urls={len(result.get('output_urls', []))} urls")

    skill_status = result.get("skill_status", "")
    if skill_status == "failed":
        _estado["errors"] = 1
        detail = result.get("detail") or result.get("error") or "sin detalle"
        _log(f"ERR Vmake reportó error: {detail}")
        # Log raw para depuración
        _log(f"ERR Raw: {str(result)[:400]}")
        return

    output_urls: list = result.get("output_urls", [])
    if not output_urls:
        _estado["errors"] = 1
        _log("ERR Vmake no devolvió URLs de resultado")
        _log(f"ERR Raw completo: {str(result)[:500]}")
        return

    output_url = output_urls[0]
    _log(f"→ URL resultado obtenida (primeros 80 chars): {output_url[:80]}...")
    _log("→ Descargando resultado...")

    stem         = Path(filename).stem
    suffix       = Path(filename).suffix or ".mp4"
    out_filename = f"{stem}_limpio{suffix}"
    out_path     = VMAKE_OUTPUT / out_filename

    try:
        _download_file(output_url, out_path)
    except Exception as e:
        _estado["errors"] = 1
        _log(f"ERR Error descargando resultado: {type(e).__name__}: {str(e)[:300]}")
        _log(f"ERR URL intentada: {output_url[:120]}")
        return

    size_mb = round(out_path.stat().st_size / (1024 * 1024), 1)
    _estado["done"]      = 1
    _estado["resultado"] = out_filename
    _log(f"OK {out_filename} ({size_mb} MB) listo para descargar")


def _download_file(url: str, dest: Path) -> None:
    """
    Descarga url a dest usando requests (con reintentos).
    Más robusto que urllib para URLs pre-firmadas de Alibaba OSS.
    """
    max_retries = 3
    last_exc    = None

    for attempt in range(1, max_retries + 1):
        try:
            with _requests.get(
                url,
                stream=True,
                timeout=(10, 120),   # 10s connect, 120s read
                headers={"User-Agent": "ProductoraClips/1.0"},
            ) as resp:
                resp.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
            return  # éxito
        except Exception as e:
            last_exc = e
            if attempt < max_retries:
                time.sleep(3 * attempt)

    raise last_exc