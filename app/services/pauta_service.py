import json
from app.core.config import PAUTA_FILE

def load_pauta():
    if PAUTA_FILE.exists():
        try:
            return json.loads(PAUTA_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return []
    return []

def save_pauta(data):
    if not isinstance(data, list):
        raise ValueError("Los datos de la pauta deben ser una lista")
    PAUTA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_valid_rows():
    pauta = load_pauta()
    return [
        r for r in pauta
        if r.get("numero") and r.get("nombre") and r.get("foto")
    ]


def actualizar_foto_en_pauta(foto_original: str, foto_editada: str) -> int:
    """
    Reemplaza en pauta.json la foto original por la foto editada en todas
    las filas donde esté seleccionada.

    Retorna la cantidad de filas actualizadas.
    """
    if not foto_original or not foto_editada:
        return 0

    pauta = load_pauta()
    updated_rows = 0

    for row in pauta:
        if row.get("foto") == foto_original:
            row["foto"] = foto_editada
            updated_rows += 1

    if updated_rows:
        save_pauta(pauta)

    return updated_rows
