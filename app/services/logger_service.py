import json
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import request, g

LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_FILE = LOG_DIR / "access.log"

# (method, path_prefix) → human-readable action
_ACTION_MAP = {
    ("POST",   "/upload"):                    "subir_foto",
    ("GET",    "/fotos/borrar_todas"):        "borrar_fotos",       # must come before /fotos
    ("GET",    "/fotos"):                     "listar_fotos",
    ("DELETE", "/fotos/borrar_todas"):        "borrar_fotos",
    ("GET",    "/thumb/"):                    "ver_preview",
    ("POST",   "/pauta"):                     "guardar_pauta",
    ("GET",    "/pauta/docx"):                "descargar_pauta_docx",
    ("GET",    "/pauta/mtime"):               "consultar_mtime_pauta",
    ("GET",    "/pauta"):                     "ver_pauta",
    ("POST",   "/generar"):                   "generar_clips",
    ("GET",    "/estado"):                    "consultar_estado",
    ("GET",    "/clips/borrar_todos"):        "borrar_clips",       # must come before /clips
    ("GET",    "/clips"):                     "listar_clips",
    ("DELETE", "/clips/borrar_todos"):        "borrar_clips",
    ("GET",    "/clip/"):                     "descargar_clip",
    ("DELETE", "/clip/"):                     "borrar_clip",
    ("GET",    "/zip"):                       "descargar_zip",
    ("GET",    "/info"):                      "info_ip",
    ("POST",   "/procesar_foto"):             "procesar_foto",
    ("POST",   "/procesar_todas"):            "procesar_todas",
    ("POST",   "/titulares/extraer"):         "extraer_titular",
    ("POST",   "/titulares/generar-premiere-todos"): "generar_premiere_todos",
    ("POST",   "/titulares/generar-premiere"):       "generar_premiere",
    ("POST",   "/titulares/generar"):         "generar_titular",
    ("GET",    "/titulares/estado-premiere"): "estado_premiere",
    ("GET",    "/titulares/estado"):          "estado_titular",
    ("GET",    "/titulares/thumb/"):          "ver_preview_titular",
    ("GET",    "/titulares/secciones"):       "listar_secciones",
    ("POST",   "/titulares/lista"):           "guardar_titulares",
    ("GET",    "/titulares/lista"):           "listar_titulares",
    ("POST",   "/titulares/preview"):         "preview_titular",
    ("GET",    "/titulares/pm-thumb/"):       "ver_pm_thumb",
    ("GET",    "/titulares/logos"):           "listar_logos",
    ("POST",   "/titulares/logo-mapping"):    "guardar_logo_mapping",
    ("GET",    "/titulares/logo-mapping"):    "ver_logo_mapping",
    ("GET",    "/"):                          "abrir_app",
}


def _infer_action(method: str, path: str) -> str:
    for (m, prefix), action in _ACTION_MAP.items():
        if method == m and path.startswith(prefix):
            return action
    return "desconocido"


class RequestLogger:
    def __init__(self, app):
        LOG_DIR.mkdir(exist_ok=True)
        app.before_request(self._before)
        app.after_request(self._after)

    @staticmethod
    def _before():
        g._log_start = time.monotonic()

    @staticmethod
    def _after(response):
        duration_ms = round((time.monotonic() - g._log_start) * 1000, 1)
        path = request.path
        forwarded = request.headers.get("X-Forwarded-For")
        ip = forwarded.split(",")[0].strip() if forwarded else request.remote_addr

        entry = {
            "ts":       datetime.now(timezone.utc).isoformat(),
            "ip":       ip,
            "method":   request.method,
            "path":     path,
            "query":    request.query_string.decode("utf-8", errors="replace") or None,
            "status":   response.status_code,
            "ms":       duration_ms,
            "action":   _infer_action(request.method, path),
            "ua":       request.headers.get("User-Agent"),
        }

        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except OSError:
            pass  # never crash the app because of logging

        return response
