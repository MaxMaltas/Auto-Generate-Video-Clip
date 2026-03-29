from flask import Blueprint, request, jsonify, send_from_directory, send_file
from app.core.config import INPUT, OUTPUT
from app.services.file_service import (
    save_uploaded_file, list_photos, list_clips, build_clips_zip
)
from app.services.pauta_service import load_pauta, save_pauta
from app.services.doc_service import build_pauta_docx
from app.services.photo_service import procesar_foto, procesar_lote

media_bp = Blueprint("media", __name__)

@media_bp.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("file")
    try:
        save_uploaded_file(f)
    except ValueError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    return jsonify({"ok": True})

@media_bp.route("/fotos")
def fotos():
    return jsonify(list_photos())

@media_bp.route("/thumb/<nombre>")
def thumb(nombre):
    return send_from_directory(INPUT, nombre)

@media_bp.route("/pauta", methods=["GET", "POST"])
def pauta():
    if request.method == "POST":
        data = request.get_json()
        if not isinstance(data, list):
            return jsonify({"ok": False, "msg": "Se esperaba una lista JSON"}), 400
        save_pauta(data)
        return jsonify({"ok": True})
    return jsonify(load_pauta())

@media_bp.route("/clips")
def clips():
    return jsonify(list_clips())

@media_bp.route("/clip/<nombre>")
def clip(nombre):
    return send_from_directory(OUTPUT, nombre)

@media_bp.route("/zip")
def zip_clips():
    return send_file(
        build_clips_zip(),
        mimetype="application/zip",
        as_attachment=True,
        download_name="clips.zip"
    )

@media_bp.route("/pauta/docx")
def pauta_docx():
    return send_file(
        build_pauta_docx(),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True,
        download_name="pauta.docx"
    )

@media_bp.route("/procesar_foto", methods=["POST"])
def procesar_foto_route():
    data = request.get_json()
    result = procesar_foto(
        nombre = data["foto"],
        x_pct  = float(data.get("x", 50)),
        y_pct  = float(data.get("y", 50)),
        scale  = float(data.get("scale", 1.0)),
        borde  = int(data.get("borde", 15))
    )
    return jsonify(result)


@media_bp.route("/procesar_todas", methods=["POST"])
def procesar_todas_route():
    items = request.get_json()
    resultados = procesar_lote(items)
    ok = sum(1 for r in resultados if r.get("ok"))
    return jsonify({"ok": True, "resultados": resultados, "total": ok})
