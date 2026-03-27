import json
from app.core.config import PAUTA_FILE

def load_pauta():
    if PAUTA_FILE.exists():
        return json.loads(PAUTA_FILE.read_text())
    return []

def save_pauta(data):
    PAUTA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2))

def get_valid_rows():
    pauta = load_pauta()
    return [
        r for r in pauta
        if r.get("numero") and r.get("nombre") and r.get("foto")
    ]