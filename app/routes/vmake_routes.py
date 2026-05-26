"""
vmake_routes.py
───────────────
Blueprint para el Proyecto 9 — Eliminación de Grafismos en Vídeo.

Endpoints:
  POST /vmake/upload          → sube un vídeo a temp/vmake/input/
  POST /vmake/procesar        → lanza el procesado en background
  GET  /vmake/estado          → estado del procesado (polling)
  GET  /vmake/resultado/<n>   → sirve el vídeo procesado
  GET  /vmake/input/<n>       → sirve el vídeo original (preview pre-procesado)
"""

import re
from pathlib import Path

from flask import Blueprint, jsonify, request, send_file, abort
from werkzeug.utils import secure_filename

from app.services.vmake_service import (
    iniciar_procesado,
    get_estado,
    VMAKE_INPUT,
    VMAKE_OUTPUT,
    VIDEO_EXTS,
)

vmake_bp = Blueprint("vmake", __name__)


def _safe_video_name(filename: str) -> str:
    """Valida que el nombre sea seguro y tenga extensión de vídeo permitida."""
    name = secure_filename(filename)
    if not name:
        return ""
    ext = Path(name).suffix.lower()
    if ext not in VIDEO_EXTS:
        return ""
    return name


@vmake_bp.route("/vmake/upload", methods=["POST"])
def upload_video():
    """Recibe un vídeo y lo guarda en temp/vmake/input/."""
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify({"ok": False, "error": "No se proporcionó ningún archivo"}), 400

    filename = _safe_video_name(f.filename)
    if not filename:
        ext = Path(f.filename).suffix.lower()
        allowed = ", ".join(sorted(VIDEO_EXTS))
        return jsonify({
            "ok": False,
            "error": f"Formato no permitido: '{ext}'. Formatos válidos: {allowed}"
        }), 400

    dest = VMAKE_INPUT / filename
    f.save(str(dest))

    size_mb = round(dest.stat().st_size / (1024 * 1024), 1)
    return jsonify({"ok": True, "filename": filename, "size_mb": size_mb})


@vmake_bp.route("/vmake/procesar", methods=["POST"])
def procesar():
    """Lanza el procesado de grafismos para el vídeo indicado."""
    data     = request.get_json(force=True) or {}
    filename = (data.get("filename") or "").strip()

    if not filename:
        return jsonify({"ok": False, "error": "Campo 'filename' requerido"}), 400

    filename = _safe_video_name(filename)
    if not filename:
        return jsonify({"ok": False, "error": "Nombre de archivo inválido"}), 400

    if not (VMAKE_INPUT / filename).exists():
        return jsonify({"ok": False, "error": f"Archivo no encontrado: {filename}"}), 404

    started = iniciar_procesado(filename)
    if not started:
        return jsonify({"ok": False, "error": "Ya hay un procesado en curso"}), 409

    return jsonify({"ok": True})


@vmake_bp.route("/vmake/estado")
def estado():
    """Devuelve el estado actual del procesado (para polling desde el frontend)."""
    return jsonify(get_estado())


@vmake_bp.route("/vmake/resultado/<nombre>")
def resultado(nombre):
    """Sirve el vídeo procesado para preview inline o descarga."""
    safe = _safe_video_name(nombre)
    if not safe:
        abort(400)
    path = VMAKE_OUTPUT / safe
    if not path.exists():
        abort(404)

    as_attachment = request.args.get("download") == "1"
    return send_file(
        str(path.resolve()),
        mimetype="video/mp4",
        as_attachment=as_attachment,
        download_name=safe,
    )


@vmake_bp.route("/vmake/input/<nombre>")
def input_preview(nombre):
    """Sirve el vídeo original subido (para preview antes de procesar)."""
    safe = _safe_video_name(nombre)
    if not safe:
        abort(400)
    path = VMAKE_INPUT / safe
    if not path.exists():
        abort(404)
    return send_file(str(path.resolve()), mimetype="video/mp4")
