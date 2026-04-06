"""
titular_premiere_service.py
───────────────────────────
Generates 50-second titular clips that replicate the 6-layer Premiere Pro
stack extracted from TITULARES 2024.xml:

  Track 1 (bottom)  Photo          – Ken Burns zoom (section-specific scale)
  Track 2           DEGRADADO      – gradient/vignette overlay (normal)
  Track 3           Section .mov   – section branding animation (normal)
  Track 4           Color overlay  – section colour tint (multiply blend)
  Track 5           Text           – headline rendered via PIL (fade-in)
  Track 6 (top)     Logo           – media outlet logo (normal)

Duration : 50 s  (1 250 frames @ 25 fps)
Output   : 1920 × 1080, H.264, yuv420p, 8 Mbps
"""

import re
import subprocess
import threading
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from PIL import Image, ImageDraw, ImageFont

from app.core.config import INPUT, OUTPUT, TEMP, WIDTH, HEIGHT, FPS

# ── Paths ────────────────────────────────────────────────────────────────────
ASSETS = Path(__file__).resolve().parent.parent.parent / "assets"
TITULAR_TEMP = TEMP / "titulares"
TITULAR_TEMP.mkdir(parents=True, exist_ok=True)

DEFAULT_LOGO = "EL PAIS_NEG.png"
MEDIOS_DIR   = ASSETS / "MEDIOS"

# ── Timing ───────────────────────────────────────────────────────────────────
TITULAR_DURATION = 50          # seconds
TITULAR_FRAMES   = TITULAR_DURATION * FPS   # 1 250 frames

# ── Section configurations (from TITULARES 2024.xml) ─────────────────────────
# zoom_start / zoom_end : Premiere scale % / 100
# center_x / center_y  : fractional offset from frame centre (Premiere horiz/vert)
# color_opacity        : opacity of the multiply-blend colour layer (0–1)
# text_y_ratio         : normalised Y position of the headline text
TEXT_X_RATIO = 0.14446   # same for all sections

SECTION_CONFIGS: dict[str, dict] = {
    "BOLETINES": {
        "zoom_start":    1.97, "zoom_end":    2.31,
        "center_x":      0.18, "center_y":    0.195,
        "color_opacity": 1.00,
        "text_y_ratio":  0.2818,
    },
    "SUCESOS": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
    },
    "PROTAS": {
        "zoom_start":    1.61, "zoom_end":    1.92,
        "center_x":      0.0,  "center_y":   0.0,
        "color_opacity": 0.92,
        "text_y_ratio":  0.2272,
    },
    "INFO": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.0,  "center_y":   0.0,
        "color_opacity": 0.88,
        "text_y_ratio":  0.2272,
    },
    "DEPORTES": {
        "zoom_start":    3.42, "zoom_end":    3.98,
        "center_x":      0.0,  "center_y":   0.181,
        "color_opacity": 0.88,
        "text_y_ratio":  0.2272,
    },
}

# ── Shared state ──────────────────────────────────────────────────────────────
_estado: dict = {
    "running": False,
    "log":     [],
    "done":    0,
    "errors":  0,
    "total":   0,
}
_lock = threading.Lock()

_SAFE_CHARS = re.compile(r"[^\w\-. ]|[/\\]", re.UNICODE)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def get_estado() -> dict:
    return dict(_estado)


def get_secciones() -> list[str]:
    return list(SECTION_CONFIGS.keys())


def iniciar_generacion(
    titular: str,
    imagen_filename: str,
    numero: str,
    seccion: str = "SUCESOS",
    logo_file: str | None = None,
    source_url: str | None = None,
) -> bool:
    with _lock:
        if _estado["running"]:
            return False
        _estado["running"] = True
    threading.Thread(
        target=_run_generar,
        args=(titular, imagen_filename, numero, seccion, logo_file, source_url),
        daemon=True,
    ).start()
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _safe_name(value: str) -> str:
    sanitized = _SAFE_CHARS.sub("", value).strip()
    while ".." in sanitized:
        sanitized = sanitized.replace("..", "")
    return sanitized.strip()


def _find_asset(candidates: list) -> Path | None:
    """Return the first existing path from the candidate list."""
    for p in candidates:
        path = Path(p)
        if path.exists():
            return path
    return None


def _norm(s: str) -> str:
    """Uppercase, strip accents, keep only alphanumeric chars."""
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9]", "", s)


def _detect_logo_from_url(url: str) -> str:
    """
    Extract the media outlet from *url* and return the matching filename
    from assets/MEDIOS/.  Falls back to DEFAULT_LOGO if nothing matches.

    Strategy:
      1. Parse the hostname, strip 'www.' and country subdomains.
      2. Normalise both the hostname key and each logo stem (_NEG suffix
         removed, spaces/accents stripped).
      3. Return the logo whose normalised name equals — or is fully
         contained in — the normalised hostname.
    """
    try:
        hostname = urlparse(url).netloc.lower()
        hostname = re.sub(r"^www\.", "", hostname)
        # Use only the registered domain part (drop TLD)
        domain_key = _norm(hostname.split(".")[0])
    except Exception:
        return DEFAULT_LOGO

    if not domain_key:
        return DEFAULT_LOGO

    candidates: list[Path] = sorted(
        [p for p in MEDIOS_DIR.glob("*") if p.suffix.lower() in (".png", ".jpg")],
        key=lambda p: p.name,
    )

    exact: Path | None = None
    partial: Path | None = None
    partial_score = 0.0

    for logo_path in candidates:
        stem      = logo_path.stem                           # e.g. "EL PAIS_NEG"
        clean     = re.sub(r"_NEG$", "", stem, flags=re.IGNORECASE)
        logo_norm = _norm(clean)                             # e.g. "ELPAIS"

        if logo_norm == domain_key:
            exact = logo_path
            break

        # Partial: logo name fully contained in domain key, or domain key
        # fully contained in logo name (guards against single-letter matches)
        if len(logo_norm) >= 3 and (
            logo_norm in domain_key or domain_key in logo_norm
        ):
            score = len(logo_norm) / max(len(domain_key), 1)
            if score > partial_score:
                partial_score = score
                partial = logo_path

    matched = exact or (partial if partial_score >= 0.5 else None)
    return matched.name if matched else DEFAULT_LOGO


def _get_section_assets(seccion: str, logo_file: str | None) -> dict:
    """Resolve available asset paths for the given section."""
    sec = seccion.upper()

    # Section animation -------------------------------------------------------
    section_mov = _find_asset([
        ASSETS / "sections" / f"{sec}.mov",
        ASSETS / "sections" / f"{sec}.mp4",
        ASSETS / f"{sec}.mov",
        ASSETS / f"{sec}.mp4",
    ])

    # Colour overlay -----------------------------------------------------------
    color_ov = _find_asset([
        #ASSETS / "colors" / f"COLOR {sec}.mp4",
        #ASSETS / "colors" / f"COLOR {sec}.mov",
        #ASSETS / "colors" / f"COLOR {sec} NEW.mp4",
        ASSETS / "colors" / f"COLOR {sec} NEW.png",
        #ASSETS / f"COLOR {sec}.mp4",
        #ASSETS / f"COLOR {sec}.mov",
        #ASSETS / f"COLOR {sec} NEW.mp4",
        ASSETS / f"COLOR {sec} NEW.png",
    ])

    # Gradient vignette --------------------------------------------------------
    degradado = None  # desactivado

    # Logo ---------------------------------------------------------------------
    if logo_file:
        logo = _find_asset([
            ASSETS / "MEDIOS" / logo_file,
            ASSETS / "logos" / logo_file,
            ASSETS / logo_file,
        ])
    else:
        logo = _find_asset([ASSETS / "logo.png"])

    return {
        "section":  section_mov,
        "color":    color_ov,
        "degradado": degradado,
        "logo":     logo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Text overlay rendering (PIL)
# ─────────────────────────────────────────────────────────────────────────────

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


def _render_text_png(titular: str, config: dict) -> tuple[Path, int]:
    """
    Render the headline as a transparent 1920×1080 PNG positioned to match
    the Premiere Pro Essential Graphics text layer coordinates from the XML.
    Returns (output_path, first_line_y).
    """
    text_x = int(TEXT_X_RATIO * WIDTH)                 # ≈277 px from left
    last_line_y = int(config["text_y_ratio"] * HEIGHT)  # fixed Y for the last line
    max_text_w = WIDTH - text_x - int(WIDTH * 0.25)  # right margin 10%

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    text_up   = titular.upper()
    font_size = 80
    min_font  = 32

    draw  = ImageDraw.Draw(canvas, "RGBA")
    font  = _get_font(font_size)
    lines = _wrap_lines(text_up, font, max_text_w, draw)

    # Shrink font until text block (anchored at last_line_y) fits vertically
    while font_size >= min_font:
        font      = _get_font(font_size)
        draw_tmp  = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        lines     = _wrap_lines(text_up, font, max_text_w, draw_tmp)
        sample_bb = draw_tmp.textbbox((0, 0), "Ag", font=font)
        line_h    = (sample_bb[3] - sample_bb[1]) + 10
        first_line_y = last_line_y - (len(lines) - 1) * line_h
        if first_line_y >= int(HEIGHT * 0.08):
            break
        font_size -= 4

    sample_bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), "Ag", font=font)
    line_h    = (sample_bb[3] - sample_bb[1]) + 10

    draw = ImageDraw.Draw(canvas, "RGBA")
    first_line_y = last_line_y - (len(lines) - 1) * line_h
    y = first_line_y
    for line in lines:
        # Drop shadow
        draw.text((text_x + 2, y + 2), line, font=font, fill=(0, 0, 0, 190))
        # White text
        draw.text((text_x,     y),     line, font=font, fill=(255, 255, 255, 255))
        y += line_h

    safe = re.sub(r"[^\w]", "_", titular[:30])
    out  = TITULAR_TEMP / f"pm_text_{safe}.png"
    canvas.save(str(out), "PNG")
    return out, first_line_y


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg command builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_ffmpeg_cmd(
    foto_path:    Path,
    text_png:     Path,
    config:       dict,
    assets:       dict,
    salida:       Path,
    first_line_y: int = 0,
) -> list[str]:
    dur = str(TITULAR_DURATION)
    cmd = ["ffmpeg", "-y"]

    # ── Inputs ───────────────────────────────────────────────────────────────
    # Input 0: photo (still image, looped for full duration)
    # Output frame rate is fixed in filter_complex (fps={FPS})
    cmd += ["-loop", "1", "-t", dur, "-i", str(foto_path)]
    idx = 1

    # Track the order of optional layers so we can reference them in filter_complex
    layer_idx: dict[str, int] = {}
    # Whether the colour overlay is a static PNG (changes blend strategy)
    color_is_png = False

    def _add_still(path: Path) -> int:
        nonlocal idx, cmd
        cmd += ["-loop", "1", "-t", dur, "-i", str(path)]
        i = idx; idx += 1; return i

    def _add_video(path: Path) -> int:
        nonlocal idx, cmd
        cmd += ["-stream_loop", "-1", "-t", dur, "-i", str(path)]
        i = idx; idx += 1; return i

    if assets.get("degradado"):
        layer_idx["degradado"] = _add_still(assets["degradado"])

    if assets.get("section"):
        layer_idx["section"] = _add_video(assets["section"])

    if assets.get("color"):
        ext = assets["color"].suffix.lower()
        if ext in (".png", ".jpg", ".jpeg"):
            color_is_png = True
            layer_idx["color"] = _add_still(assets["color"])
        else:
            layer_idx["color"] = _add_video(assets["color"])

    # Text PNG (always present)
    text_idx = _add_still(text_png)

    if assets.get("logo"):
        layer_idx["logo"] = _add_still(assets["logo"])

    # ── Filter complex ────────────────────────────────────────────────────────
    flt: list[str] = []

    # Step 1 – Scale photo to 1920×1080 (cover + centre crop)
    flt.append(
        f"[0:v]scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT}:(in_w-out_w)/2:(in_h-out_h)/2,"
        f"fps={FPS},"
        f"setsar=1,"
        f"setpts=PTS-STARTPTS[photo_static]"
    )
    current = "photo_static"

    # Step 3 – Degradado overlay (normal blend)
    if "degradado" in layer_idx:
        i = layer_idx["degradado"]
        flt.append(f"[{i}:v]scale={WIDTH}:{HEIGHT},setpts=PTS-STARTPTS[deg]")
        flt.append(f"[{current}][deg]overlay=format=auto[with_deg]")
        current = "with_deg"

    # Step 4 – Section .mov overlay (normal blend)
    if "section" in layer_idx:
        i = layer_idx["section"]
        flt.append(f"[{i}:v]scale={WIDTH}:{HEIGHT},setpts=PTS-STARTPTS[sec]")
        flt.append(f"[{current}][sec]overlay=format=auto[with_sec]")
        current = "with_sec"

    # Step 5 – Colour overlay
    if "color" in layer_idx:
        i       = layer_idx["color"]
        opacity = config.get("color_opacity", 0.88)

        if color_is_png:
            # PNG sólido: multiply con un PNG opaco eliminaría casi todos los canales.
            # En su lugar usamos overlay con opacidad baja (≈20%) para un tinte suave.
            # Cuando tengas los .mov originales de Premiere, el multiply funcionará bien.
            png_opacity = min(opacity, 1)  # ~20% máximo
            flt.append(
                f"[{i}:v]scale={WIDTH}:{HEIGHT},"
                f"format=rgba,"
                f"colorchannelmixer=aa={png_opacity:.3f},"
                f"setpts=PTS-STARTPTS[col_tint]"
            )
            flt.append(f"[{current}][col_tint]overlay=format=auto[with_col]")
        else:
            # Vídeo .mov/.mp4: multiply blend auténtico (como en Premiere Pro)
            flt.append(
                f"[{current}]format=rgb24[base_rgb];"
                f"[{i}:v]scale={WIDTH}:{HEIGHT},format=rgb24,setpts=PTS-STARTPTS[col_rgb];"
                f"[base_rgb][col_rgb]blend=all_mode=multiply:all_opacity={opacity},"
                f"format=yuv420p[with_col]"
            )
        current = "with_col"

    # Step 6 – Text overlay (no fade)
    flt.append(
        f"[{text_idx}:v]"
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black@0,"
        f"setpts=PTS-STARTPTS[txt_f]"
    )
    flt.append(f"[{current}][txt_f]overlay=format=auto[with_txt]")
    current = "with_txt"

    # Step 7 – Logo overlay (top, normal blend)
    # X aligned with text; Y = 30 px above the first line of text
    if "logo" in layer_idx:
        i = layer_idx["logo"]
        logo_x = int(TEXT_X_RATIO * WIDTH)
        logo_y = first_line_y - 30   # ih is subtracted so top-edge lands 30 px above text
        flt.append(
            f"[{i}:v]setpts=PTS-STARTPTS[logo_l]"
        )
        flt.append(
            f"[{current}][logo_l]overlay=x={logo_x}:y={logo_y}-overlay_h:format=auto[with_logo]"
        )
        current = "with_logo"

    filter_complex = "; ".join(flt)

    cmd += [
        "-filter_complex", filter_complex,
        "-map", f"[{current}]",
        "-vcodec",  "libx264",
        "-pix_fmt", "yuv420p",
        "-r",       str(FPS),
        "-t",       dur,
        "-b:v",     "8M",
        "-preset",  "fast",
        "-crf",     "18",
        str(salida),
    ]

    return cmd


# ─────────────────────────────────────────────────────────────────────────────
# Thread worker
# ─────────────────────────────────────────────────────────────────────────────

def _run_generar(
    titular: str,
    imagen_filename: str,
    numero: str,
    seccion: str,
    logo_file: str | None,
    source_url: str | None,
) -> None:
    _estado.update({"log": [], "done": 0, "errors": 0, "total": 1})
    try:
        sec    = seccion.upper()
        config = SECTION_CONFIGS.get(sec, SECTION_CONFIGS["SUCESOS"])

        foto_path = INPUT / _safe_name(imagen_filename)
        if not foto_path.exists():
            # Fall back: look in TITULAR_TEMP (downloaded via URL extractor)
            foto_path = TITULAR_TEMP / _safe_name(imagen_filename)
        if not foto_path.exists():
            raise FileNotFoundError(f"Foto no encontrada: {imagen_filename}")

        # Auto-detect logo from URL when no explicit logo was provided
        if not logo_file and source_url:
            logo_file = _detect_logo_from_url(source_url)
            _estado["log"].append(f"→ Logo detectado: {logo_file}")
        elif not logo_file:
            logo_file = DEFAULT_LOGO

        assets = _get_section_assets(sec, logo_file)

        # Log which assets were found
        found = [k for k, v in assets.items() if v]
        missing = [k for k, v in assets.items() if not v]
        _estado["log"].append(f"→ Sección: {sec}")
        _estado["log"].append(f"→ Assets encontrados: {', '.join(found) or 'ninguno'}")
        if missing:
            _estado["log"].append(f"ℹ Assets no encontrados (se omiten): {', '.join(missing)}")

        _estado["log"].append("→ Renderizando texto...")
        text_png, first_line_y = _render_text_png(titular, config)

        num    = re.sub(r"[^\d]", "", str(numero)).zfill(2) or "01"
        nombre = _safe_name(titular[:50].upper()) or "TITULAR"
        salida = OUTPUT / f"{num} {nombre}.mp4"

        _estado["log"].append(f"→ [{num}] Construyendo pipeline FFmpeg...")

        cmd = _build_ffmpeg_cmd(foto_path, text_png, config, assets, salida, first_line_y)

        _estado["log"].append(f"→ Renderizando {TITULAR_DURATION}s (puede tardar varios minutos)...")

        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

        if result.returncode != 0:
            # Surface the last 300 chars of stderr for diagnosis
            err_tail = (result.stderr or "")[-300:].strip()
            raise RuntimeError(err_tail or "FFmpeg devolvió código de error")

        _estado["done"] = 1
        _estado["log"].append(f"✓ {num} {nombre}.mp4")

    except Exception as exc:
        _estado["errors"] = 1
        _estado["log"].append(f"✗ Error: {str(exc)[:200]}")
    finally:
        _estado["running"] = False
