import re
import threading
import ipaddress
import socket
import requests
import ffmpeg
from typing import Any
from pathlib import Path
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont

from app.core.config import BG_VIDEO, LOGO, OUTPUT, TEMP, DURATION, WIDTH, HEIGHT, FPS

TITULAR_TEMP = TEMP / "titulares"
TITULAR_TEMP.mkdir(parents=True, exist_ok=True)

_SAFE_CHARS = re.compile(r"[^\w\-. ]|[/\\]", re.UNICODE)

_estado = {
    "running": False,
    "log": [],
    "done": 0,
    "errors": 0,
    "total": 0,
}
_lock = threading.Lock()

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

MAX_DOWNLOAD_BYTES = 15 * 1024 * 1024  # 15 MB


def _is_private_host(hostname: str) -> bool:
    """Best-effort private/loopback/link-local detection to reduce SSRF risk."""
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return True
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_unspecified
            or ip.is_reserved
        ):
            return True
    return False


def _validate_public_http_url(raw_url: str) -> str:
    parsed = urlparse((raw_url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("La URL debe usar http o https")
    if not parsed.netloc:
        raise ValueError("URL inválida")
    hostname = parsed.hostname or ""
    if _is_private_host(hostname):
        raise ValueError("No se permiten URLs internas o privadas")
    return parsed.geturl()

# ── EXTRACTION ────────────────────────────────────────────────────────────────

def extraer_de_url(url: str) -> dict[str, Any]:
    """
    Intenta extraer titular e imagen probando cada estrategia en orden.
    Pasa a la siguiente si la anterior falla o no devuelve titular.
    """
    orden = [
        ("headers_h1", _estrategia_headers_h1),
        ("og_tags", _estrategia_og_tags),
        ("backend_proxy", _estrategia_backend_proxy),
    ]

    for key, fn in orden:
        try:
            data = fn(url)
            if (data.get("titular") or "").strip():
                return {
                    "titular": data["titular"],
                    "imagen_url": data.get("imagen_url"),
                    "strategy": key,
                }
        except Exception:
            continue

    return {"titular": None, "imagen_url": None, "strategy": None}


def _fetch_soup(url: str, headers: dict[str, str] | None = None, timeout: int = 15):
    req_headers = dict(HEADERS)
    if headers:
        req_headers.update(headers)
    resp = requests.get(url, headers=req_headers, timeout=timeout, allow_redirects=True)
    resp.raise_for_status()
    return BeautifulSoup(resp.content, "html.parser")


def _estrategia_headers_h1(url: str) -> dict[str, str | None]:
    soup = _fetch_soup(url)
    h1 = soup.find("h1")
    titular = h1.get_text(strip=True) if h1 else None
    return {
        "titular": titular,
        "imagen_url": _extraer_imagen(soup, url),
    }


def _estrategia_og_tags(url: str) -> dict[str, str | None]:
    soup = _fetch_soup(url)
    og_title = soup.find("meta", property="og:title")
    og_image = soup.find("meta", property="og:image")
    titular = og_title.get("content", "").strip() if og_title else None
    imagen = og_image.get("content", "").strip() if og_image else None
    return {
        "titular": titular or None,
        "imagen_url": urljoin(url, imagen) if imagen else None,
    }


def _estrategia_backend_proxy(url: str) -> dict[str, str | None]:
    """
    Variante server-side explícita para forzar headers de navegador y referer.
    """
    soup = _fetch_soup(url, headers={"Referer": url, "Upgrade-Insecure-Requests": "1"})
    return {
        "titular": _extraer_titular(soup),
        "imagen_url": _extraer_imagen(soup, url),
    }



def _extraer_titular(soup) -> str | None:
    og = soup.find("meta", property="og:title")
    if og and og.get("content", "").strip():
        return og["content"].strip()
    tw = soup.find("meta", attrs={"name": "twitter:title"})
    if tw and tw.get("content", "").strip():
        return tw["content"].strip()
    h1 = soup.find("h1")
    if h1 and h1.get_text(strip=True):
        return h1.get_text(strip=True)
    title = soup.find("title")
    if title and title.string:
        return re.split(r"\s*[|\-\u2013\u2014]\s*", title.string.strip())[0].strip()
    return None


def _extraer_imagen(soup, base_url: str) -> str | None:
    og = soup.find("meta", property="og:image")
    if og and og.get("content", "").strip():
        return urljoin(base_url, og["content"].strip())
    tw = soup.find("meta", attrs={"name": "twitter:image"})
    if tw and tw.get("content", "").strip():
        return urljoin(base_url, tw["content"].strip())
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or ""
        if not src or src.startswith("data:"):
            continue
        if re.search(r"logo|icon|pixel|tracking|avatar|sprite|blank", src, re.I):
            continue
        try:
            w = int(img.get("width", "0"))
            h = int(img.get("height", "0"))
            if (0 < w < 100) or (0 < h < 100):
                continue
        except ValueError:
            pass
        return urljoin(base_url, src)
    return None

# ── IMAGE DOWNLOAD ────────────────────────────────────────────────────────────

def descargar_imagen(imagen_url: str) -> str:
    """Download image to TITULAR_TEMP. Returns the saved filename."""
    imagen_url = _validate_public_http_url(imagen_url)
    TITULAR_TEMP.mkdir(parents=True, exist_ok=True)
    path_part = imagen_url.split("?")[0].rstrip("/")
    ext = Path(path_part).suffix.lower()
    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
        ext = ".jpg"
    raw_name = path_part.split("/")[-1]
    safe = re.sub(r"[^\w]", "_", raw_name)[:40]
    filename = safe + ext
    dest = TITULAR_TEMP / filename
    r = requests.get(imagen_url, headers=HEADERS, timeout=20, stream=True)
    r.raise_for_status()
    content_type = (r.headers.get("Content-Type") or "").lower()
    if content_type and not content_type.startswith("image/"):
        raise ValueError("La URL no apunta a una imagen")

    total = 0
    with open(dest, "wb") as f:
        for chunk in r.iter_content(8192):
            total += len(chunk)
            if total > MAX_DOWNLOAD_BYTES:
                f.close()
                dest.unlink(missing_ok=True)
                raise ValueError("La imagen excede el tamaño máximo permitido (15 MB)")
            f.write(chunk)
    return filename

# ── IMAGE PREPARATION (PIL) ───────────────────────────────────────────────────

def _get_font(size: int) -> ImageFont.FreeTypeFont:
    for path in [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibrib.ttf",
        "C:/Windows/Fonts/calibri.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _wrap_lines(text: str, font, max_width: int, draw: ImageDraw.Draw) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def preparar_imagen_con_titular(img_filename: str, titular: str) -> str:
    """
    Compose a 1920×1080 frame:
    - Web image as full-frame background (cover/crop).
    - Titular in UPPERCASE, centered in a semi-transparent rounded rectangle
      respecting broadcast title-safe margins (10% each side = 192px H / 108px V).

    Returns filename of the prepared PNG saved in TITULAR_TEMP.
    """
    # ── Broadcast safe area constants (EBU R95 / SMPTE RP 218) ──────────────
    # Action safe:  3.5% → ~67 px H / ~38 px V
    # Title safe:  10.0% → 192 px H / 108 px V  ← we use this for the text box
    TITLE_SAFE_H = round(WIDTH  * 0.10)   # 192 px
    TITLE_SAFE_V = round(HEIGHT * 0.10)   # 108 px
    SAFE_W = WIDTH  - TITLE_SAFE_H * 2    # 1536 px  (max text rect width)
    SAFE_H = HEIGHT - TITLE_SAFE_V * 2    # 864  px  (max text rect height)

    # ── Background: web image scaled to COVER the full frame ─────────────────
    src = TITULAR_TEMP / img_filename
    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
    try:
        photo = Image.open(src).convert("RGBA")
        # Cover: scale so the image fills the frame, then center-crop
        ratio = max(WIDTH / photo.width, HEIGHT / photo.height)
        new_w = int(photo.width  * ratio)
        new_h = int(photo.height * ratio)
        photo = photo.resize((new_w, new_h), Image.LANCZOS)
        x = (WIDTH  - new_w) // 2
        y = (HEIGHT - new_h) // 2
        canvas.paste(photo, (x, y), photo)
    except Exception:
        pass  # black background if photo fails

    # ── Measure text ─────────────────────────────────────────────────────────
    text_up = titular.upper()
    font_size = 68
    min_font  = 36
    inner_h_pad = 56   # horizontal padding inside the rectangle
    inner_v_pad = 44   # vertical padding inside the rectangle
    corner_r    = 18   # rounded corner radius

    draw = ImageDraw.Draw(canvas, "RGBA")
    font = _get_font(font_size)
    max_text_w = SAFE_W - inner_h_pad * 2

    # Reduce font until text fits horizontally and the box stays within safe area
    while font_size >= min_font:
        font = _get_font(font_size)
        draw_temp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines = _wrap_lines(text_up, font, max_text_w, draw_temp)
        sample_bb = draw_temp.textbbox((0, 0), "Ag", font=font)
        line_h = (sample_bb[3] - sample_bb[1]) + 12
        box_h = len(lines) * line_h + inner_v_pad * 2
        if box_h <= SAFE_H:
            break
        font_size -= 4

    sample_bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), "Ag", font=font)
    line_h = (sample_bb[3] - sample_bb[1]) + 12

    # Final text block dimensions
    block_w = SAFE_W
    block_h = len(lines) * line_h + inner_v_pad * 2

    # Center the rectangle on the frame
    rect_x = (WIDTH  - block_w) // 2
    rect_y = (HEIGHT - block_h) // 2

    # ── Draw semi-transparent rectangle with rounded corners ─────────────────
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rounded_rectangle(
        [(rect_x, rect_y), (rect_x + block_w, rect_y + block_h)],
        radius=corner_r,
        fill=(0, 0, 0, 185),
    )
    canvas = Image.alpha_composite(canvas, overlay)

    # ── Draw text lines ───────────────────────────────────────────────────────
    draw = ImageDraw.Draw(canvas, "RGBA")
    y_text = rect_y + inner_v_pad
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        text_w = bb[2] - bb[0]
        x_text = (WIDTH - text_w) // 2
        # Drop shadow
        draw.text((x_text + 2, y_text + 2), line, font=font, fill=(0, 0, 0, 160))
        # Main text
        draw.text((x_text, y_text), line, font=font, fill=(255, 255, 255, 255))
        y_text += line_h

    out_name = re.sub(r"\.\w+$", "", img_filename) + "_titular.png"
    out_path = TITULAR_TEMP / out_name
    canvas.convert("RGB").save(str(out_path), "PNG")
    return out_name

# ── STATE ─────────────────────────────────────────────────────────────────────

def get_estado() -> dict:
    return dict(_estado)

# ── CLIP GENERATION ───────────────────────────────────────────────────────────

def _safe_name(value: str) -> str:
    sanitized = _SAFE_CHARS.sub("", value).strip()
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "")
    return sanitized.strip()


def iniciar_generacion(titular: str, imagen_filename: str, numero: str) -> bool:
    with _lock:
        if _estado["running"]:
            return False
        _estado["running"] = True
    threading.Thread(
        target=_run_generar,
        args=(titular, imagen_filename, numero),
        daemon=True,
    ).start()
    return True


def _run_generar(titular: str, imagen_filename: str, numero: str) -> None:
    _estado.update({"log": [], "done": 0, "errors": 0, "total": 1})
    try:
        num = re.sub(r"[^\d]", "", str(numero)).zfill(2) or "01"
        nombre = _safe_name(titular[:50].upper()) or "TITULAR"

        _estado["log"].append("→ Preparando imagen con titular...")
        prepared = preparar_imagen_con_titular(imagen_filename, titular)
        foto_path = TITULAR_TEMP / prepared

        if not foto_path.exists():
            raise FileNotFoundError("Imagen preparada no encontrada")

        salida = OUTPUT / f"{num} {nombre}.mp4"
        _estado["log"].append(f"→ [{num}] {nombre} — generando clip...")

        bg = (
            ffmpeg
            .input(str(BG_VIDEO), stream_loop=-1, t=DURATION)
            .filter("scale", WIDTH, HEIGHT, force_original_aspect_ratio="increase")
            .filter("crop", WIDTH, HEIGHT)
            .filter("setpts", "PTS-STARTPTS")
        )

        foto = (
            ffmpeg
            .input(str(foto_path), loop=1, t=DURATION)
            .filter("scale", WIDTH, HEIGHT, force_original_aspect_ratio="increase")
            .filter("crop", WIDTH, HEIGHT)
            .filter("setpts", "PTS-STARTPTS")
        )

        logo = (
            ffmpeg
            .input(str(LOGO), loop=1, t=DURATION)
            .filter("setpts", "PTS-STARTPTS")
        )

        comp = ffmpeg.overlay(bg, foto)
        comp = ffmpeg.overlay(comp, logo)

        try:
            audio = ffmpeg.input(str(BG_VIDEO), t=DURATION).audio
            (
                ffmpeg
                .output(
                    comp, audio, str(salida),
                    vcodec="libx264", acodec="aac",
                    pix_fmt="yuv420p", r=FPS, t=DURATION,
                    **{"b:v": "8M", "preset": "fast", "crf": "18"},
                )
                .overwrite_output()
                .run(quiet=True)
            )
        except ffmpeg.Error:
            (
                ffmpeg
                .output(
                    comp, str(salida),
                    vcodec="libx264",
                    pix_fmt="yuv420p", r=FPS, t=DURATION,
                    **{"b:v": "8M", "preset": "fast", "crf": "18"},
                )
                .overwrite_output()
                .run(quiet=True)
            )

        _estado["done"] += 1
        _estado["log"].append(f"✓ {num} {nombre}.mp4")

    except Exception as e:
        _estado["errors"] += 1
        _estado["log"].append(f"✗ Error: {str(e)[:120]}")
    finally:
        _estado["running"] = False
