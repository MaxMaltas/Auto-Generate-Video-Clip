import re
from flask import Blueprint, request, jsonify, send_file, abort

from app.services.titular_service import (
    extraer_de_url,
    descargar_imagen,
    iniciar_generacion,
    get_estado,
    TITULAR_TEMP,
)

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
        return jsonify({
            "ok": True,
            "titular": result["titular"],
            "imagen_url": result["imagen_url"],
            "imagen": imagen_filename,
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
        abort(404)
    return send_file(str(path.resolve()))
