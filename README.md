# 🎬 ProductoraClips

Aplicación interna para redacción audiovisual que automatiza la creación de clips a partir de imágenes, pauta y titulares de noticias.

Incluye dos flujos principales:

1. **Pauta clásica**: subida de fotos, edición, generación y exportación de clips.
2. **Titulares estilo Premiere**: extracción desde URL, selección de sección/logo y generación individual o masiva.

---

## 🚀 Funcionalidades actuales

### 📋 Flujo de pauta (clips clásicos)

- Subida de imágenes desde navegador (drag & drop).
- Pauta editable con campos: número, nombre, texto y foto.
- Sincronización de pauta entre clientes mediante `mtime` (útil en LAN con varios redactores).
- Guardado manual y autosave.
- Exportación de pauta a **Word (.docx)**.
- Generación automática de clips con FFmpeg.
- Monitor de estado/progreso.
- Previsualización de clips generados.
- Descarga individual y descarga masiva en ZIP.
- Borrado masivo de fotos y clips.

### 🖼️ Editor de fotos

- Vista previa en canvas 1920x1080.
- Ajuste de escala, posición X/Y y grosor de borde.
- Acciones rápidas: centrar, fill, fit.
- Procesado individual o por lote.
- Salida de fotos editadas en `input/fotos/*_editada.png`.

### 🗞️ Módulo de titulares

- Extracción automática de titular e imagen desde URL (metadatos OG/Twitter + fallback HTML).
- Descarga automática de imagen de noticia.
- Generación de titular simple (fondo + caja de texto + branding base).
- **Generación estilo Premiere** con composición multicapa (foto, degradado, animación de sección, color, texto, logo).
- Configuración por secciones (`BOLETINES`, `SUCESOS`, `PROTAS`, `INFO`, `DEPORTES`).
- Soporte de ajustes de tipografía: tamaño, espaciado y brillo de color.
- Detección automática de logo por dominio de la URL.
- Gestión de mapeos manuales dominio → logo.
- Gestión de lista de titulares con generación masiva (`generar-premiere-todos`) y previews.

### 🌐 Operación en red local

- La app se levanta en `0.0.0.0:8080`.
- Se muestran URLs local y de red para compartir con redacción.

---

## 🧱 Stack técnico

- **Backend**: Python + Flask.
- **Render/Procesado**: FFmpeg (`ffmpeg-python` + llamadas a binario FFmpeg).
- **Imágenes/Títulos**: Pillow.
- **Extracción web de titulares**: `requests` + `beautifulsoup4`.
- **Exportación Word**: `python-docx`.
- **Frontend**: HTML + CSS + JavaScript vanilla (UI en pestañas).

---

## 📁 Estructura del proyecto

```text
.
├── run.py
├── requirements.txt
├── app/
│   ├── __init__.py
│   ├── core/
│   │   ├── config.py
│   │   └── state.py
│   ├── routes/
│   │   ├── main_routes.py
│   │   ├── media_routes.py
│   │   ├── process_routes.py
│   │   └── titular_routes.py
│   ├── services/
│   │   ├── clip_service.py
│   │   ├── doc_service.py
│   │   ├── file_service.py
│   │   ├── info_services.py
│   │   ├── pauta_service.py
│   │   ├── photo_service.py
│   │   ├── titular_service.py
│   │   └── titular_premiere_service.py
│   └── templates/
│       └── index.html
├── assets/
│   ├── MEDIOS/
│   ├── logo_mappings.json
│   └── ...
├── input/fotos/
├── output/
├── temp/
└── pauta.json
```

---

## ⚙️ Requisitos

### Sistema

- Python **3.10+**.
- FFmpeg instalado y accesible por PATH.

### Dependencias Python

Instalación base:

```bash
pip install -r requirements.txt
```

Para el módulo de titulares (extracción por URL), asegúrate de tener también:

```bash
pip install requests beautifulsoup4
```

> Nota: `requirements.txt` actual contiene `flask`, `ffmpeg-python`, `python-docx` y `pillow`.

---

## 🪟 Instalación rápida en Windows

1. Instala Python desde https://www.python.org/downloads/ y marca **“Add Python to PATH”**.
2. Instala FFmpeg desde https://ffmpeg.org/download.html y añade `...\ffmpeg\bin` al PATH.
3. Clona y entra al proyecto:

```bash
git clone <TU_REPO>
cd Auto-Generate-Video-Clip
```

4. Crea y activa entorno virtual:

```bash
python -m venv venv
venv\Scripts\activate
```

5. Instala dependencias:

```bash
pip install -r requirements.txt
pip install requests beautifulsoup4
```

6. Ejecuta:

```bash
python run.py
```

---

## 🍎 Instalación rápida en macOS

```bash
brew install python ffmpeg
git clone <TU_REPO>
cd Auto-Generate-Video-Clip
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python run.py
```

---

## ▶️ Ejecución

Lanza:

```bash
python run.py
```

Accesos habituales:

- Local: `http://localhost:8080`
- LAN: `http://IP_DEL_EQUIPO:8080`

El script imprime automáticamente la IP local detectada para compartirla con redacción.

---

## 📌 Carpetas y archivos clave

- `assets/`: vídeos/overlays/logos base.
- `assets/MEDIOS/`: logos de medios para titulares.
- `assets/logo_mappings.json`: mapeos manuales dominio → logo.
- `input/fotos/`: fotos originales y editadas.
- `output/`: clips MP4 finales.
- `temp/`: temporales de generación y previews.
- `pauta.json`: estado persistido de la pauta.

---

## ✅ Recomendaciones operativas

- Procesa las fotos en la pestaña **Editor** antes de generar clips clásicos.
- Para titulares, revisa logo detectado por dominio y corrige mapping cuando sea necesario.
- Si trabajáis varios usuarios en LAN, mantened una única pauta activa para evitar sobreescrituras de contenido.
- Limpia `output/` periódicamente para evitar acumulación de clips antiguos.
