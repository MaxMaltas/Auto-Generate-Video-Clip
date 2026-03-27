import socket
import webbrowser
from app import create_app

app = create_app()

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

    webbrowser.open("http://localhost:8080")
    app.run(host="0.0.0.0", port=8080, debug=True)