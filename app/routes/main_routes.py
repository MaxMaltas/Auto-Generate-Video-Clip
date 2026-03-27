from flask import Blueprint, jsonify
from app.services.info_services import get_local_ip

main_bp = Blueprint("main", __name__)

@main_bp.route("/info")
def info():
    return jsonify({"ip": get_local_ip()})