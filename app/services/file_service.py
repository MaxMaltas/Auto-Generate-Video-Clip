import io
import zipfile
from app.core.config import INPUT, OUTPUT

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG'}

def save_uploaded_file(file_storage):
    if file_storage:
        file_storage.save(INPUT / file_storage.filename)

def list_photos():
    return sorted([
        f.name for f in INPUT.iterdir()
        if f.suffix in IMAGE_EXTS
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