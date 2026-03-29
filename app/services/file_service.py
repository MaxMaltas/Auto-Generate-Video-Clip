import io
import zipfile
from werkzeug.utils import secure_filename
from app.core.config import INPUT, OUTPUT

IMAGE_EXTS = {'.jpg', '.jpeg', '.png'}

def save_uploaded_file(file_storage):
    """Save an uploaded image file to the INPUT directory.

    Returns the sanitized filename on success, or raises ValueError when the
    file is missing or its extension is not allowed.
    """
    if not file_storage or not file_storage.filename:
        raise ValueError("No se proporcionó ningún archivo")

    filename = secure_filename(file_storage.filename)
    if not filename:
        raise ValueError("Nombre de archivo inválido")

    ext = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    if ext not in IMAGE_EXTS:
        raise ValueError(f"Tipo de archivo no permitido: {ext or '(sin extensión)'}")

    file_storage.save(INPUT / filename)
    return filename

def list_photos():
    return sorted([
        f.name for f in INPUT.iterdir()
        if f.suffix.lower() in IMAGE_EXTS
    ])

def list_clips():
    return sorted([f.name for f in OUTPUT.glob("*.mp4")])

def build_clips_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in OUTPUT.glob("*.mp4"):
            zf.write(f, f.name)
    buf.seek(0)
    return buf