# 🎬 ProductoraClips

Herramienta interna para la automatización de clips audiovisuales a partir de imágenes y una pauta editable.

Permite a un equipo de redacción subir fotos, definir una pauta y generar automáticamente clips listos para emisión.

---

# 🚀 Funcionalidades

* 📁 Subida de imágenes desde navegador
* 📋 Creación de pauta editable (número, nombre, texto opcional, foto)
* ⚙️ Generación automática de clips con FFmpeg
* 🎬 Previsualización y descarga de clips
* 📦 Descarga masiva en ZIP
* 📝 Exportación de pauta en formato Word (.docx)
* 🌐 Acceso desde red local (LAN)

---

# 🧠 Cómo funciona

El flujo de trabajo es:

1. Subir imágenes
2. Crear pauta del día
3. Generar clips automáticamente
4. Descargar o revisar resultados

Internamente:

* Backend: Python + Flask
* Procesado: FFmpeg
* Frontend: HTML + JS (vanilla)
* Exportación Word: python-docx

---

# 📦 Estructura del proyecto

```
productoraclips/
├── run.py
├── app/
│   ├── routes/
│   ├── services/
│   ├── core/
│   └── templates/
├── assets/
├── input/fotos/
├── output/
└── temp/
```

---

# ⚙️ Requisitos

## Software necesario

* Python 3.10 o superior
* FFmpeg instalado en el sistema

---

# 🪟 Instalación en Windows

## 1. Instalar Python

Descargar desde:
https://www.python.org/downloads/

⚠️ IMPORTANTE: marcar
✔️ "Add Python to PATH"

---

## 2. Instalar FFmpeg

1. Descargar desde:
   https://ffmpeg.org/download.html

2. Descomprimir

3. Añadir la carpeta `bin` al PATH:

Ejemplo:

```
C:\ffmpeg\bin
```

---

## 3. Clonar el proyecto

```bash
git clone https://github.com/TU_USUARIO/productoraclips.git
cd productoraclips
```

---

## 4. Crear entorno virtual

```bash
python -m venv venv
venv\Scripts\activate
```

---

## 5. Instalar dependencias

```bash
pip install flask ffmpeg-python python-docx pillow requests beautifulsoup4
```

---

## 6. Ejecutar

```bash
python run.py
```

Abrir en navegador:

```
http://localhost:8080
```

---

# 🍎 Instalación en macOS

## 1. Instalar Homebrew (si no lo tienes)

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## 2. Instalar FFmpeg

```bash
brew install ffmpeg
```

---

## 3. Instalar Python

```bash
brew install python
```

---

## 4. Clonar proyecto

```bash
git clone https://github.com/TU_USUARIO/productoraclips.git
cd productoraclips
```

---

## 5. Entorno virtual

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 6. Dependencias

```bash
pip install flask ffmpeg-python python-docx pillow requests beautifulsoup4
```

---

## 7. Ejecutar

```bash
python run.py
```

Abrir:

```
http://localhost:8080
```

---

# 🌐 Acceso en red local

La app también es accesible desde otros dispositivos en la misma red:

```
http://IP_DEL_EQUIPO:8080
```

Ejemplo:

```
http://192.168.1.35:8080
```

---

# 📁 Carpetas importantes

* `assets/` → vídeos base y logo
* `input/fotos/` → imágenes subidas
* `output/` → clips generados
* `temp/` → archivos temporales
* `pauta.json` → datos de la pauta

---

# 📝 Formato de pauta

Cada entrada tiene:

```
01 - NOMBRE - Texto opcional
```

Ejemplo:

```
01 - MANUEL
02 - JESUS - Cumple 44 años
```

---

# 🎬 Generación de clips

Cada clip se genera con:

* Fondo de vídeo
* Imagen con zoom dinámico
* Overlay de logo
* Duración fija (10s)
* Resolución Full HD (1920x1080)

---

# 🧩 Dependencias Python

* Flask → servidor web
* ffmpeg-python → wrapper de FFmpeg
* python-docx → generación de documentos Word

---

# ⚠️ Notas importantes

* FFmpeg debe estar correctamente instalado y accesible en PATH
* No es un servidor de producción (uso interno / local)
* No incluye autenticación (entorno controlado)

---

# 🧱 Futuras mejoras

* Integración con WhatsApp / formularios
* Autogeneración de pauta
* Base de datos (SQLite)
* Sistema de plantillas
* Paralelización del render
* Dockerización

---

# 👤 Autor

Proyecto desarrollado como herramienta de automatización para producción audiovisual.

---

# 📄 Licencia

Uso interno / privado (definir según necesidades)

