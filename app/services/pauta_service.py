import json
from app.core.config import PAUTA_FILE


TIPOS_PAUTA_VALIDOS = {"FOTO", "CUBRIR", "TOTAL"}


def _normalizar_tipo(tipo):
    valor = str(tipo or "").strip().upper()
    return valor if valor in TIPOS_PAUTA_VALIDOS else "FOTO"


def load_pauta():
    if PAUTA_FILE.exists():
        try:
            data = json.loads(PAUTA_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                for row in data:
                    if isinstance(row, dict):
                        row["tipo"] = _normalizar_tipo(row.get("tipo"))
                return data
            return []
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_pauta(data):
    if not isinstance(data, list):
        raise ValueError("Los datos de la pauta deben ser una lista")
    for row in data:
        if isinstance(row, dict):
            row["tipo"] = _normalizar_tipo(row.get("tipo"))
    PAUTA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_valid_rows():
    pauta = load_pauta()
    return [
        r for r in pauta
        if r.get("numero") and r.get("nombre") and r.get("foto")
    ]
