import re
from flask import Blueprint, request, jsonify, send_file, abort

from app.services.titular_service import (
    extraer_de_url,
    descargar_imagen,
    iniciar_generacion,
    get_estado,
    TITULAR_TEMP,
)
import app.services.titular_premiere_service as pm_svc
from app.services.titular_premiere_service import TITULAR_TEMP as PM_TITULAR_TEMP
from app.core.config import INPUT

titular_bp = Blueprint("titular", __name__)


@titular_bp.route("/titulares/extraer", methods=["POST"])
def extraer():
    data = request.get_json(force=True)
    url = (data.get("url") or "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URL requerida"})
    try:
        result = extraer_de_url(url)
        if not result["titular"]:
            return jsonify({"ok": False, "error": "No se pudo extraer el titular"})
        imagen_filename = None
        if result["imagen_url"]:
            imagen_filename = descargar_imagen(result["imagen_url"])
        logo_file = pm_svc._detect_logo_from_url(url) if url else None
        logo_height = pm_svc.get_logo_height(logo_file) if logo_file else None
        return jsonify({
            "ok": True,
            "titular": result["titular"],
            "imagen_url": result["imagen_url"],
            "strategy": result.get("strategy"),
            "imagen": imagen_filename,
            "logo_file": logo_file,
            "logo_height": logo_height,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)[:200]})


@titular_bp.route("/titulares/generar", methods=["POST"])
def generar():
    data = request.get_json(force=True)
    titular = (data.get("titular") or "").strip()
    imagen  = (data.get("imagen")  or "").strip()
    numero  = (data.get("numero")  or "01").strip()
    if not titular or not imagen:
        return jsonify({"ok": False, "error": "Titular e imagen requeridos"})
    started = iniciar_generacion(titular, imagen, numero)
    if not started:
        return jsonify({"ok": False, "error": "Ya hay una generación en curso"})
    return jsonify({"ok": True})


@titular_bp.route("/titulares/estado")
def estado():
    return jsonify(get_estado())


@titular_bp.route("/titulares/thumb/<nombre>")
def thumb(nombre):
    if re.search(r"[/\\]|\.\.", nombre):
        abort(400)
    path = TITULAR_TEMP / nombre
    if not path.exists():
        path = INPUT / nombre
    if not path.exists():
        abort(404)
    return send_file(str(path.resolve()))


# ── Premiere-style generation ─────────────────────────────────────────────────

@titular_bp.route("/titulares/secciones")
def secciones():
    return jsonify(pm_svc.get_secciones())


@titular_bp.route("/titulares/generar-premiere", methods=["POST"])
def generar_premiere():
    data             = request.get_json(force=True)
    titular          = (data.get("titular")    or "").strip()
    imagen           = (data.get("imagen")     or "").strip()
    numero           = (data.get("numero")     or "01").strip()
    seccion          = (data.get("seccion")    or "SUCESOS").strip().upper()
    logo             = (data.get("logo")       or "").strip() or None
    source_url       = (data.get("source_url") or "").strip() or None
    font_size_raw    = data.get("font_size")
    letter_spacing   = int(data.get("letter_spacing", -2) or 0)
    color_brightness = float(data.get("color_brightness", 1.0) or 1.0)
    font_size        = int(font_size_raw) if font_size_raw else None
    logo_width_raw   = data.get("logo_width")
    logo_width       = int(logo_width_raw) if logo_width_raw else None

    if not titular or not imagen:
        return jsonify({"ok": False, "error": "Titular e imagen requeridos"})

    started = pm_svc.iniciar_generacion(
        titular, imagen, numero, seccion, logo, source_url,
        font_size, letter_spacing, color_brightness, logo_width,
    )
    if not started:
        return jsonify({"ok": False, "error": "Ya hay una generación en curso"})
    return jsonify({"ok": True})


@titular_bp.route("/titulares/generar-premiere-todos", methods=["POST"])
def generar_premiere_todos():
    items = request.get_json(force=True)
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "Se esperaba un array de titulares"})
    started = pm_svc.iniciar_generacion_lista(items)
    if not started:
        return jsonify({"ok": False, "error": "Ya hay una generación en curso"})
    return jsonify({"ok": True})


@titular_bp.route("/titulares/estado-premiere")
def estado_premiere():
    return jsonify(pm_svc.get_estado())


# ── Multi-titular list ────────────────────────────────────────────────────────

@titular_bp.route("/titulares/lista", methods=["GET"])
def lista_get():
    return jsonify(pm_svc.get_titulares_list())


@titular_bp.route("/titulares/lista", methods=["POST"])
def lista_set():
    items = request.get_json(force=True)
    if not isinstance(items, list):
        return jsonify({"ok": False, "error": "Se esperaba un array"})
    pm_svc.set_titulares_list(items)
    return jsonify({"ok": True})


@titular_bp.route("/titulares/preview", methods=["POST"])
def preview_titular():
    item = request.get_json(force=True)
    result = pm_svc.generar_preview(item)
    return jsonify(result)


@titular_bp.route("/titulares/pm-thumb/<nombre>")
def pm_thumb(nombre):
    if re.search(r"[/\\]|\.\.", nombre):
        abort(400)
    path = PM_TITULAR_TEMP / nombre
    if not path.exists():
        abort(404)
    return send_file(str(path.resolve()))


# ── Logo management ───────────────────────────────────────────────────────────

@titular_bp.route("/titulares/logos")
def logos_list():
    return jsonify(pm_svc.get_logos_list())


@titular_bp.route("/titulares/upload-logo", methods=["POST"])
def upload_logo():
    file = request.files.get("file")
    try:
        filename = pm_svc.save_uploaded_logo(file)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": True, "filename": filename})


@titular_bp.route("/titulares/logo-mapping", methods=["GET"])
def logo_mapping_get():
    return jsonify(pm_svc.get_logo_mappings())


@titular_bp.route("/titulares/logo-mapping", methods=["POST"])
def logo_mapping_set():
    data            = request.get_json(force=True)
    domain_key      = (data.get("domain_key") or "").strip().lower()
    logo_file       = (data.get("logo_file")  or "").strip()
    logo_height_raw = data.get("logo_height")
    logo_height     = int(logo_height_raw) if logo_height_raw else None
    if not domain_key or not logo_file:
        return jsonify({"ok": False, "error": "domain_key y logo_file requeridos"})
    pm_svc.save_logo_mapping(domain_key, logo_file, logo_height)
    return jsonify({"ok": True})
