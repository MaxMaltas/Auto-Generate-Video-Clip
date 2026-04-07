import os
from PIL import Image

def procesar_logos():
    # --- CONFIGURACIÓN ---
    CARPETA_ENTRADA = 'logos_originales'  # Carpeta donde están tus 400 archivos
    CARPETA_SALIDA = 'MEDIOS'         # Carpeta donde se guardará el resultado
    ANCHO_FINAL = 1000
    ALTO_FINAL = 170
    # Margen de seguridad (0.9 = el logo usará el 90% del espacio máximo)
    PADDING = 0.9 

    # Crear la carpeta de salida si no existe
    if not os.path.exists(CARPETA_SALIDA):
        os.makedirs(CARPETA_SALIDA)

    # Dimensiones máximas que puede tener el logo dentro del lienzo
    max_w = int(ANCHO_FINAL * PADDING)
    max_h = int(ALTO_FINAL * PADDING)

    archivos = [f for f in os.listdir(CARPETA_ENTRADA) if f.lower().endswith('.png')]
    print(f"Encontrados {len(archivos)} archivos. Iniciando proceso...")

    for nombre_archivo in archivos:
        path_input = os.path.join(CARPETA_ENTRADA, nombre_archivo)
        nombre_salida = nombre_archivo.replace('_NEG', '')
        path_output = os.path.join(CARPETA_SALIDA, nombre_salida)

        try:
            with Image.open(path_input) as img:
                img = img.convert("RGBA")

                # 1. REESCALADO INTELIGENTE
                # thumbnail mantiene la proporción y solo reduce si es necesario
                img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

                # Si tras el reescalado la imagen es más pequeña que 84px de alto, se escala al mínimo
                ALTO_MINIMO = 84
                if img.height < ALTO_MINIMO:
                    ratio = ALTO_MINIMO / img.height
                    nuevo_ancho = int(img.width * ratio)
                    img = img.resize((nuevo_ancho, ALTO_MINIMO), Image.Resampling.LANCZOS)

                # 2. CREACIÓN DEL LIENZO (CANVAS)
                # Creamos un rectángulo de 1000x170 totalmente transparente (0,0,0,0)
                lienzo = Image.new("RGBA", (ANCHO_FINAL, ALTO_FINAL), (0, 0, 0, 0))

                # 3. POSICIONADO A LA IZQUIERDA
                offset_x = 0
                offset_y = (ALTO_FINAL - img.height) // 2

                # 4. PEGADO Y GUARDADO
                lienzo.paste(img, (offset_x, offset_y), img)
                lienzo.save(path_output, "PNG")
                
            print(f"✅ Procesado: {nombre_archivo}")

        except Exception as e:
            print(f"❌ Error con {nombre_archivo}: {e}")

    print(f"\n¡Listo! Revisa la carpeta '{CARPETA_SALIDA}'")

if __name__ == "__main__":
    procesar_logos()
