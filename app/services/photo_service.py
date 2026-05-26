from PIL import Image, ImageDraw
from app.core.config import INPUT

CANVAS_W   = 1920
CANVAS_H   = 1080
GUIDE_TOP  = 96
GUIDE_BOT  = CANVAS_H - 96   # 984


def procesar_foto(nombre: str, x_pct: float, y_pct: float,
                  scale: float, borde: int = 15) -> dict:
    """
    Genera un PNG 1920x1080 con fondo transparente,
    la foto posicionada/escalada, recortada a las guías (96px arriba/abajo)
    y con marco blanco interior aplicado tras el recorte.
    Guarda en input/fotos/ con sufijo _editada.png y borra el original.
    """
    foto_path = INPUT / nombre
    if not foto_path.exists():
        return {"ok": False, "error": "Foto no encontrada"}

    try:
        img   = Image.open(foto_path).convert("RGBA")
        new_w = int(img.width  * scale)
        new_h = int(img.height * scale)
        img   = img.resize((new_w, new_h), Image.LANCZOS)

        cx = int(CANVAS_W * x_pct / 100)
        cy = int(CANVAS_H * y_pct / 100)
        px = cx - new_w // 2
        py = cy - new_h // 2

        # ── Recorte por guías ──────────────────────────────────────────
        # Si la foto sobrepasa GUIDE_TOP o GUIDE_BOT, se recorta
        crop_top    = max(0, GUIDE_TOP - py)          # píxeles a quitar arriba
        crop_bottom = max(0, (py + new_h) - GUIDE_BOT) # píxeles a quitar abajo

        if crop_top > 0 or crop_bottom > 0:
            img_bottom = new_h - crop_bottom
            img = img.crop((0, crop_top, new_w, img_bottom))
            py     = py + crop_top
            new_h  = img.height

        # ── Pegar en canvas ───────────────────────────────────────────
        canvas = Image.new("RGBA", (CANVAS_W, CANVAS_H), (0, 0, 0, 0))
        canvas.paste(img, (px, py), img)

        # ── Marco blanco (se aplica DESPUÉS del recorte) ──────────────
        if borde > 0:
            draw   = ImageDraw.Draw(canvas)
            left   = max(px, 0)
            top    = max(py, 0)
            right  = min(px + new_w, CANVAS_W)
            bottom = min(py + new_h, CANVAS_H)
            for i in range(borde):
                draw.rectangle(
                    [left + i, top + i, right - 1 - i, bottom - 1 - i],
                    outline=(255, 255, 255, 255)
                )

        out_name  = foto_path.stem + "_editada.png"
        out_path  = INPUT / out_name
        canvas.save(out_path, "PNG")

        # ── Borrar original ───────────────────────────────────────────
        if foto_path.resolve() != out_path.resolve():
            foto_path.unlink()

        return {"ok": True, "resultado": out_name}

    except Exception as e:
        return {"ok": False, "error": str(e)}


def procesar_lote(items: list) -> list:
    """Procesa una lista de fotos con sus ajustes."""
    return [
        {**procesar_foto(
            item["foto"],
            float(item.get("x", 50)),
            float(item.get("y", 50)),
            float(item.get("scale", 1.0)),
            int(item.get("borde", 15))
        ), "foto": item["foto"]}
        for item in items
    ]