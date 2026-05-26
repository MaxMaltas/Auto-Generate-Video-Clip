import os
import socket
import webbrowser
from pathlib import Path


def _load_dotenv(path: Path) -> None:
    """
    Carga variables de entorno desde un fichero .env sin dependencias externas.
    Formato soportado: KEY=valor (líneas en blanco y comentarios # ignorados).
    No sobreescribe variables ya definidas en el entorno del sistema.
    """
    if not path.exists():
        return
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key   = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


# Carga .env antes de importar la app para que los servicios vean las variables
_load_dotenv(Path(__file__).parent / ".env")

from app import create_app  # noqa: E402

app = create_app()
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


if __name__ == "__main__":
    ip = get_local_ip()
    print("\n🎬 ProductoraClips Portal")
    print(f"   Local:  http://localhost:8080")
    print(f"   Red:    http://{ip}:8080")
    print("\n   Comparte la URL de Red con el redactor.")
    print("   Ctrl+C para cerrar.\n")

    # Avisar si faltan credenciales Vmake
    if not os.environ.get("MT_AK") or not os.environ.get("MT_SK"):
        print("⚠️  Vmake: MT_AK / MT_SK no configurados. La pestaña 'Limpiar Vídeo' no funcionará.")
        print("   Crea un fichero .env basándote en .env.example\n")

    debug = os.environ.get("FLASK_DEBUG", "0") == "1"
    webbrowser.open("http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=debug)
