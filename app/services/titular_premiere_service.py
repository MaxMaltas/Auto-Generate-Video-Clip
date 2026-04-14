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

import json
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

DEFAULT_LOGO      = "EL PAIS_NEG.png"
MEDIOS_DIR        = ASSETS / "MEDIOS"
LOGO_MAPPINGS_FILE = ASSETS / "logo_mappings.json"

# ── Logo mappings helpers ─────────────────────────────────────────────────────
_mappings_lock = threading.Lock()


def _load_mappings() -> dict:
    """Return {domain_key: logo_filename} from the JSON file."""
    try:
        if LOGO_MAPPINGS_FILE.exists():
            return json.loads(LOGO_MAPPINGS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def _save_mappings(data: dict) -> None:
    LOGO_MAPPINGS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def get_logos_list() -> list[str]:
    """Sorted list of all logo filenames in MEDIOS_DIR."""
    return sorted(
        p.name for p in MEDIOS_DIR.glob("*")
        if p.suffix.lower() in (".png", ".jpg")
    )


def get_logo_mappings() -> dict:
    with _mappings_lock:
        return _load_mappings()


def save_logo_mapping(domain_key: str, logo_filename: str) -> None:
    """Persist a domain → logo association."""
    with _mappings_lock:
        data = _load_mappings()
        data[domain_key.strip().lower()] = logo_filename
        _save_mappings(data)


def _domain_key_from_url(url: str) -> str:
    """Extract the normalised domain key from a URL (same logic as detection)."""
    try:
        hostname = urlparse(url).netloc.lower()
        hostname = re.sub(r"^www\.", "", hostname)
        return hostname.split(".")[0]
    except Exception:
        return ""

# ── Timing ───────────────────────────────────────────────────────────────────
TITULAR_DURATION = 50          # seconds
TITULAR_FRAMES   = TITULAR_DURATION * FPS   # 1 250 frames

# ── Section configurations (from TITULARES 2024.xml) ─────────────────────────
# zoom_start / zoom_end : Premiere scale % / 100
# center_x / center_y  : fractional offset from frame centre (Premiere horiz/vert)
# color_opacity        : opacity of the multiply-blend colour layer (0–1)
# text_y_ratio         : normalised Y position of the headline text
TEXT_X_RATIO = 0.14446   # same for all sections
LOGO_WIDTH = 250
LOGO_TEXT_GAP = 20

SECTION_CONFIGS: dict[str, dict] = {
    "BOLETINES": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
    },
    "SUCESOS": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
    },
    "PROTAS": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
    },
    "INFO": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
    },
    "DEPORTES": {
        "zoom_start":    1.61, "zoom_end":    2.11,
        "center_x":      0.019, "center_y":  0.0,
        "color_opacity": 0.50,
        "text_y_ratio":  0.62,
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
    font_size: int | None = None,
    letter_spacing: int = -2,
    color_brightness: float = 1.0,
    logo_width: int | None = None,
) -> bool:
    with _lock:
        if _estado["running"]:
            return False
        _estado["running"] = True
    threading.Thread(
        target=_run_generar,
        args=(titular, imagen_filename, numero, seccion, logo_file, source_url,
              font_size, letter_spacing, color_brightness, logo_width),
        daemon=True,
    ).start()
    return True


def iniciar_generacion_lista(items: list[dict]) -> bool:
    with _lock:
        if _estado["running"]:
            return False
        _estado["running"] = True
    threading.Thread(
        target=_run_generar_lista,
        args=(list(items),),
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


def _get_logo_layout(first_line_y: int, logo_width: int = LOGO_WIDTH) -> dict[str, int]:
    """Shared logo geometry so preview and final render stay aligned."""
    return {
        "x": int(TEXT_X_RATIO * WIDTH),
        "width": logo_width,
        # The real top edge is resolved with the scaled logo height in each renderer.
        "baseline_y": first_line_y - LOGO_TEXT_GAP,
    }


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
      0. Check manual logo_mappings.json first (exact raw domain key).
      1. Parse the hostname, strip 'www.' and country subdomains.
      2. Normalise both the hostname key and each logo stem (_NEG suffix
         removed, spaces/accents stripped).
      3. Return the logo whose normalised name equals — or is fully
         contained in — the normalised hostname.
    """
    try:
        hostname = urlparse(url).netloc.lower()
        hostname = re.sub(r"^www\.", "", hostname)
        raw_key  = hostname.split(".")[0]          # e.g. "elpais"
        domain_key = _norm(raw_key)
    except Exception:
        return DEFAULT_LOGO

    if not domain_key:
        return DEFAULT_LOGO

    # ── Step 0: manual mapping takes priority ─────────────────────────────────
    mappings = _load_mappings()
    if raw_key in mappings:
        logo_name = mappings[raw_key]
        if (MEDIOS_DIR / logo_name).exists():
            return logo_name

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
        # Proxima Nova Extra Bold — macOS
	    # "/Users/aruba/Library/Fonts/ProximaNova-ExtrabldIt.otf",
	    "/Users/aruba/Library/Fonts/Proxima Nova Extrabold.otf",
        "/Library/Fonts/ProximaNova-Extrabld.ttf",
        "/Library/Fonts/Proxima Nova ExtraBold.ttf",
        "/Library/Fonts/ProximaNovaExtraBold.ttf",
        "/Library/Fonts/proximanova-extrabold.ttf",
        # También puede estar en la carpeta del usuario
        "/Users/Shared/Library/Fonts/ProximaNova-Extrabld.ttf",
        "~/Library/Fonts/ProximaNova-Extrabld.ttf",
        # Fallbacks macOS
        "/Library/Fonts/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/ArialHB.ttc",
        "/Library/Fonts/Arial.ttf",
        # Fallbacks Windows (por si el código se ejecuta en ambos entornos)
        "C:/Windows/Fonts/Proxima Nova Extrabold.otf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _measure_text_width(draw_tmp, text: str, font, letter_spacing: int = -2) -> int:
    if not text:
        return 0
    if letter_spacing == 0:
        bb = draw_tmp.textbbox((0, 0), text, font=font)
        return bb[2] - bb[0]
    total = 0
    for i, char in enumerate(text):
        bb = draw_tmp.textbbox((0, 0), char, font=font)
        total += bb[2] - bb[0]
        if i < len(text) - 1:
            total += letter_spacing
    return total


def _draw_text_spaced(draw, x: int, y: int, text: str, font, fill, letter_spacing: int = -2) -> None:
    if letter_spacing == 0:
        draw.text((x, y), text, font=font, fill=fill)
        return
    for char in text:
        draw.text((x, y), char, font=font, fill=fill)
        bb = draw.textbbox((0, 0), char, font=font)
        x += (bb[2] - bb[0]) + letter_spacing


def _wrap_lines(text: str, font, max_width: int, draw: ImageDraw.Draw, letter_spacing: int = -2) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = (current + " " + word).strip()
        if _measure_text_width(draw, candidate, font, letter_spacing) <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [text]


def _render_text_png(
    titular: str,
    config: dict,
    font_size_override: int | None = None,
    letter_spacing: int = -2,
) -> tuple[Path, int]:
    """
    Render the headline as a transparent 1920×1080 PNG positioned to match
    the Premiere Pro Essential Graphics text layer coordinates from the XML.
    Returns (output_path, first_line_y).
    """
    text_x = int(TEXT_X_RATIO * WIDTH)                 # ≈277 px from left
    last_line_y = int(config["text_y_ratio"] * HEIGHT)  # fixed Y for the last line
    max_text_w = WIDTH - text_x - int(WIDTH * 0.25)  # right margin

    canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    text_up   = titular
    font_size = font_size_override if font_size_override else 100
    min_font  = 32

    draw_tmp = ImageDraw.Draw(Image.new("RGBA", (1, 1)))

    if font_size_override:
        # Use the fixed size as-is, just compute line wrapping
        font      = _get_font(font_size)
        lines     = _wrap_lines(text_up, font, max_text_w, draw_tmp, letter_spacing)
        sample_bb = draw_tmp.textbbox((0, 0), "Ag", font=font)
        line_h    = (sample_bb[3] - sample_bb[1]) + 10
    else:
        # Shrink font until text block (anchored at last_line_y) fits vertically
        font  = _get_font(font_size)
        lines = _wrap_lines(text_up, font, max_text_w, draw_tmp, letter_spacing)
        while font_size >= min_font:
            font      = _get_font(font_size)
            draw_tmp  = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
            lines     = _wrap_lines(text_up, font, max_text_w, draw_tmp, letter_spacing)
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
        _draw_text_spaced(draw, text_x + 2, y + 2, line, font, (0, 0, 0, 190), letter_spacing)
        # White text
        _draw_text_spaced(draw, text_x,     y,     line, font, (255, 255, 255, 255), letter_spacing)
        y += line_h

    safe = re.sub(r"[^\w]", "_", titular[:30])
    out  = TITULAR_TEMP / f"pm_text_{safe}.png"
    canvas.save(str(out), "PNG")
    return out, first_line_y


# ─────────────────────────────────────────────────────────────────────────────
# FFmpeg command builder
# ─────────────────────────────────────────────────────────────────────────────

def _build_ffmpeg_cmd(
    foto_path:        Path,
    text_png:         Path,
    config:           dict,
    assets:           dict,
    salida:           Path,
    first_line_y:     int   = 0,
    color_brightness: float = 1.0,
    logo_width:       int   = LOGO_WIDTH,
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
        # brightness: 1.0 = original, <1 = darker, >1 = brighter (clamp to 0–3)
        brightness_filter = ""
        if color_brightness != 1.0:
            b = max(0.0, min(3.0, color_brightness))
            brightness_filter = f"eq=brightness={b - 1.0:.3f},"

        if color_is_png:
            png_opacity = min(opacity, 1.0)
            flt.append(
                f"[{i}:v]scale={WIDTH}:{HEIGHT},"
                f"format=rgba,"
                f"{brightness_filter}"
                f"colorchannelmixer=aa={png_opacity:.3f},"
                f"setpts=PTS-STARTPTS[col_tint]"
            )
            flt.append(f"[{current}][col_tint]overlay=format=auto[with_col]")
        else:
            # Vídeo .mov/.mp4: multiply blend auténtico (como en Premiere Pro)
            flt.append(
                f"[{current}]format=rgb24[base_rgb];"
                f"[{i}:v]scale={WIDTH}:{HEIGHT},{brightness_filter}format=rgb24,setpts=PTS-STARTPTS[col_rgb];"
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
        logo_layout = _get_logo_layout(first_line_y, logo_width)
        flt.append(
            f"[{i}:v]scale={logo_layout['width']}:-1,setpts=PTS-STARTPTS[logo_l]"
        )
        flt.append(
            f"[{current}][logo_l]overlay="
            f"x={logo_layout['x']}:y={logo_layout['baseline_y']}-overlay_h:format=auto[with_logo]"
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
# Multi-titular list  (stored in memory, not persisted)
# ─────────────────────────────────────────────────────────────────────────────

# Each entry: { id, titular, imagen, seccion, logo_file, source_url,
#               font_size, letter_spacing, color_brightness, preview }
_titulares_list: list[dict] = []
_titulares_lock = threading.Lock()


def get_titulares_list() -> list[dict]:
    with _titulares_lock:
        return list(_titulares_list)


def set_titulares_list(items: list[dict]) -> None:
    with _titulares_lock:
        _titulares_list.clear()
        _titulares_list.extend(items)


def generar_preview(item: dict) -> dict:
    """
    Composite a still 1920×1080 preview PNG:
      Track 1 – photo (scaled + cropped)
      Track 4 – colour overlay PNG (section tint)
      Track 5 – text layer
      Track 6 – logo
    Returns {"ok": bool, "preview": filename | None, "error": str | None}.
    """
    try:
        titular          = (item.get("titular") or "").strip()
        seccion          = (item.get("seccion") or "SUCESOS").upper()
        imagen_filename  = (item.get("imagen") or "").strip()
        source_url       = (item.get("source_url") or "").strip() or None
        logo_file        = (item.get("logo_file") or "").strip() or None
        color_brightness = float(item.get("color_brightness") or 1.0)
        _fs            = item.get("font_size")
        font_size      = int(_fs) if _fs is not None else None
        _ls            = item.get("letter_spacing")
        letter_spacing = int(_ls) if _ls is not None else -2
        _lw            = item.get("logo_width")
        logo_width     = int(_lw) if _lw else LOGO_WIDTH

        config = SECTION_CONFIGS.get(seccion, SECTION_CONFIGS["SUCESOS"])

        # ── Track 1: Photo ────────────────────────────────────────────────────
        canvas = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 255))
        if imagen_filename:
            foto_path = INPUT / _safe_name(imagen_filename)
            if not foto_path.exists():
                foto_path = TITULAR_TEMP / _safe_name(imagen_filename)
            if foto_path.exists():
                with Image.open(foto_path) as foto:
                    foto = foto.convert("RGBA")
                    # cover + centre crop
                    scale = max(WIDTH / foto.width, HEIGHT / foto.height)
                    new_w = int(foto.width  * scale)
                    new_h = int(foto.height * scale)
                    foto  = foto.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    x_off = (new_w - WIDTH)  // 2
                    y_off = (new_h - HEIGHT) // 2
                    foto  = foto.crop((x_off, y_off, x_off + WIDTH, y_off + HEIGHT))
                    canvas.paste(foto, (0, 0))

        # ── Track 4: Colour overlay ────────────────────────────────────────────
        if not logo_file and source_url:
            logo_file = _detect_logo_from_url(source_url)
        elif not logo_file:
            logo_file = DEFAULT_LOGO

        assets = _get_section_assets(seccion, logo_file)

        if assets.get("color"):
            ext = assets["color"].suffix.lower()
            if ext in (".png", ".jpg", ".jpeg"):
                with Image.open(assets["color"]) as col:
                    col = col.convert("RGBA").resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)
                    opacity = config.get("color_opacity", 0.88)
                    # Apply brightness by scaling pixel values
                    if color_brightness != 1.0:
                        from PIL import ImageEnhance
                        col = ImageEnhance.Brightness(col).enhance(color_brightness)
                    # Adjust alpha channel by opacity
                    a = col.split()[3]
                    a = a.point(lambda v: int(v * opacity))
                    col.putalpha(a)
                    canvas = Image.alpha_composite(canvas, col)

        # ── Track 5: Text ─────────────────────────────────────────────────────
        text_png, first_line_y = _render_text_png(titular, config, font_size, letter_spacing)
        with Image.open(text_png) as txt:
            canvas = Image.alpha_composite(canvas, txt.convert("RGBA"))

        # ── Track 6: Logo ─────────────────────────────────────────────────────
        if assets.get("logo"):
            with Image.open(assets["logo"]) as logo:
                logo = logo.convert("RGBA")
                logo_layout = _get_logo_layout(first_line_y, logo_width)
                ratio  = logo_layout["width"] / logo.width
                logo_h = int(logo.height * ratio)
                logo   = logo.resize((logo_layout["width"], logo_h), Image.Resampling.LANCZOS)
                logo_y = logo_layout["baseline_y"] - logo_h
                canvas.paste(logo, (logo_layout["x"], max(0, logo_y)), logo)

        # ── Save ──────────────────────────────────────────────────────────────
        safe = re.sub(r"[^\w]", "_", titular[:30])
        out  = TITULAR_TEMP / f"pm_preview_{safe}.jpg"
        canvas.convert("RGB").save(str(out), "JPEG", quality=88)
        return {"ok": True, "preview": out.name, "error": None}

    except Exception as exc:
        return {"ok": False, "preview": None, "error": str(exc)[:300]}


# ─────────────────────────────────────────────────────────────────────────────
# Thread worker
# ─────────────────────────────────────────────────────────────────────────────

def _generar_clip_item(
    item: dict,
    numero: str,
    item_index: int | None = None,
    total_items: int | None = None,
) -> str:
    titular = (item.get("titular") or "").strip()
    imagen_filename = (item.get("imagen") or "").strip()
    seccion = (item.get("seccion") or "SUCESOS").strip().upper()
    logo_file = (item.get("logo_file") or item.get("logo") or "").strip() or None
    source_url = (item.get("source_url") or "").strip() or None
    font_size_raw = item.get("font_size")
    letter_spacing = int(item.get("letter_spacing") or 0)
    color_brightness = float(item.get("color_brightness") or 1.0)
    font_size = int(font_size_raw) if font_size_raw not in (None, "") else None
    logo_width_raw = item.get("logo_width")
    logo_width = int(logo_width_raw) if logo_width_raw else LOGO_WIDTH

    if not titular:
        raise ValueError("Titular vacío")
    if not imagen_filename:
        raise ValueError("Imagen no especificada")

    sec = seccion.upper()
    config = SECTION_CONFIGS.get(sec, SECTION_CONFIGS["SUCESOS"])

    foto_path = INPUT / _safe_name(imagen_filename)
    if not foto_path.exists():
        foto_path = TITULAR_TEMP / _safe_name(imagen_filename)
    if not foto_path.exists():
        raise FileNotFoundError(f"Foto no encontrada: {imagen_filename}")

    if item_index is not None and total_items is not None:
        _estado["log"].append(f"→ Procesando titular {item_index}/{total_items}")

    if not logo_file and source_url:
        logo_file = _detect_logo_from_url(source_url)
        _estado["log"].append(f"→ Logo detectado: {logo_file}")
    elif not logo_file:
        logo_file = DEFAULT_LOGO

    assets = _get_section_assets(sec, logo_file)
    found = [k for k, v in assets.items() if v]
    missing = [k for k, v in assets.items() if not v]
    _estado["log"].append(f"→ Sección: {sec}")
    _estado["log"].append(f"→ Assets encontrados: {', '.join(found) or 'ninguno'}")
    if missing:
        _estado["log"].append(f"ℹ Assets no encontrados (se omiten): {', '.join(missing)}")

    _estado["log"].append("→ Renderizando texto...")
    text_png, first_line_y = _render_text_png(titular, config, font_size, letter_spacing)

    nombre = _safe_name(titular[:50].upper()) or "TITULAR"
    salida = OUTPUT / f"01 TIT {nombre}.mp4"

    _estado["log"].append(f"→ [01 TIT] Construyendo pipeline FFmpeg...")
    cmd = _build_ffmpeg_cmd(
        foto_path, text_png, config, assets, salida,
        first_line_y, color_brightness, logo_width,
    )

    _estado["log"].append(f"→ Renderizando {TITULAR_DURATION}s (puede tardar varios minutos)...")
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")

    if result.returncode != 0:
        err_tail = (result.stderr or "")[-300:].strip()
        raise RuntimeError(err_tail or "FFmpeg devolvió código de error")

    return f"01 TIT {nombre}.mp4"


def _run_generar(
    titular: str,
    imagen_filename: str,
    numero: str,
    seccion: str,
    logo_file: str | None,
    source_url: str | None,
    font_size: int | None = None,
    letter_spacing: int = -2,
    color_brightness: float = 1.0,
    logo_width: int | None = None,
) -> None:
    _estado.update({"log": [], "done": 0, "errors": 0, "total": 1})
    try:
        nombre_archivo = _generar_clip_item(
            {
                "titular": titular,
                "imagen": imagen_filename,
                "seccion": seccion,
                "logo_file": logo_file,
                "source_url": source_url,
                "font_size": font_size,
                "letter_spacing": letter_spacing,
                "color_brightness": color_brightness,
                "logo_width": logo_width,
            },
            numero,
        )
        _estado["done"] = 1
        _estado["log"].append(f"OK {nombre_archivo}")

    except Exception as exc:
        _estado["errors"] = 1
        _estado["log"].append(f"ERR Error: {str(exc)[:200]}")
    finally:
        _estado["running"] = False


def _run_generar_lista(items: list[dict]) -> None:
    valid_items = [item for item in items if isinstance(item, dict)]
    _estado.update({"log": [], "done": 0, "errors": 0, "total": len(valid_items)})
    try:
        if not valid_items:
            raise ValueError("No hay titulares en la lista")

        for idx, item in enumerate(valid_items, start=1):
            numero = str(idx).zfill(2)
            try:
                nombre_archivo = _generar_clip_item(item, numero, idx, len(valid_items))
                _estado["done"] = idx
                _estado["log"].append(f"OK {nombre_archivo}")
            except Exception as exc:
                _estado["errors"] += 1
                _estado["done"] = idx
                _estado["log"].append(f"ERR [{numero}] {str(exc)[:200]}")
    finally:
        _estado["running"] = False
