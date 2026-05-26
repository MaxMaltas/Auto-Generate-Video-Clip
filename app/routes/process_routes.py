from flask import Blueprint, jsonify
from app.core.state import estado
from app.services.clip_service import start_generation

process_bp = Blueprint("process", __name__)

@process_bp.route("/generar", methods=["POST"])
def generar():
    ok = start_generation()
    if not ok:
        return jsonify({"ok": False, "msg": "Ya hay un proceso en curso"})
    return jsonify({"ok": True})

@process_bp.route("/estado")
def get_estado():
    return jsonify(estado)