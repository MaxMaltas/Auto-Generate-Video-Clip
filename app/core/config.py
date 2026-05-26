from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
ASSETS = BASE / "assets"
INPUT = BASE / "input" / "fotos"
OUTPUT = BASE / "output"
TEMP = BASE / "temp"

for d in [INPUT, OUTPUT, TEMP]:
    d.mkdir(parents=True, exist_ok=True)

BG_VIDEO = ASSETS / "background.mp4"
LOGO = ASSETS / "logo.png"

DURATION = 10
WIDTH = 1920
HEIGHT = 1080
FPS = 25

PAUTA_FILE = BASE / "pauta.json"