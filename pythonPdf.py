import os
import base64
from PyPDF2 import PdfReader, PdfWriter
import fitz  # PyMuPDF
from flask import Flask, request, jsonify

app = Flask(__name__)

def verificar_base64(cadena_base64):
    """
    Verifica si el string base64 es valido

    Args:
        cadena_base64 (str): Cadena en formato base64

    Returns:
        tuple: (es_valido, datos_decodificados)
    """
    try:
        datos_decodificados = base64.b64decode(cadena_base64)
        if not datos_decodificados:
            return False, "La cadena base64 no contiene datos."
        return True, datos_decodificados
    except Exception as e:
        return False, f"Error al decodificar base64: {str(e)}"

def extraer_imagenes_de_pdf(ruta_pdf):
    """
    Extrae imagenes de un PDF escaneado

    Args:
        ruta_pdf (str): Ruta al archivo PDF de entrada

    Returns:
        list: Lista de rutas a las imagenes extraidas
    """
    imagenes = []
    try:
        doc = fitz.open(ruta_pdf)
        for num_pagina in range(doc.page_count):
            pagina = doc.load_page(num_pagina)
            lista_img = pagina.get_images(full=True)
            for img in lista_img:
                xref = img[0]
                base_img = doc.extract_image(xref)
                datos_img = base_img["image"]
                nombre_img = f"imagen_{num_pagina+1}_{xref}.png"
                with open(nombre_img, "wb") as archivo_img:
                    archivo_img.write(datos_img)
                imagenes.append(nombre_img)
        doc.close()
    except Exception as e:
        print(f"Error al extraer imagenes: {str(e)}")
    return imagenes

def crear_pdf_desde_imagenes(lista_imagenes, salida_pdf):
    """
    Crea un PDF a partir de imagenes extraidas

    Args:
        lista_imagenes (list): Lista de archivos de imagen
        salida_pdf (str): Ruta del PDF de salida
    """
    doc = fitz.open()  # Documento vacio para agregar imagenes
    for archivo_imagen in lista_imagenes:
        img = fitz.open(archivo_imagen)  # Abrir la imagen
        pix = img[0].get_pixmap()  # Obtener el pixmap de la imagen
        rect = fitz.Rect(0, 0, pix.width, pix.height)  # Dimensiones de la imagen
        pagina_pdf = doc.new_page(width=rect.width, height=rect.height)  # Nueva pagina con el tamano de la imagen
        pagina_pdf.insert_image(rect, filename=archivo_imagen)  # Insertar imagen en la pagina
    doc.save(salida_pdf)
    doc.close()

def verificar_formato_pdf(ruta_pdf):
    """
    Verifica el formato interno del PDF.
    Se considera valido si en alguna pagina se encuentra texto o imagenes.

    Args:
        ruta_pdf (str): Ruta al archivo PDF

    Returns:
        bool: True si el PDF es valido, False en otro caso
    """
    try:
        doc = fitz.open(ruta_pdf)
        es_valido = False
        # Verificar si alguna pagina tiene texto legible
        for pagina in doc:
            texto = pagina.get_text().strip()
            if texto:
                es_valido = True
                break
        # Si no se encontro texto, checar si existen imagenes
        if not es_valido:
            for pagina in doc:
                if pagina.get_images(full=True):
                    es_valido = True
                    break
        doc.close()
        return es_valido
    except Exception:
        return False

def normalizar_pdf(ruta_pdf):
    """
    Normaliza un PDF invalido recreandolo y reemplaza el archivo original.
    Se utiliza un archivo temporal para escribir el PDF normalizado y luego se reemplaza.

    Args:
        ruta_pdf (str): Ruta al archivo PDF de entrada

    Returns:
        tuple: (ruta_pdf_normalizado, lista_imagenes, mensaje_error)
    """
    try:
        # Intentar abrir el PDF con PdfReader
        try:
            lector_pdf = PdfReader(open(ruta_pdf, 'rb'))
        except Exception as error_apertura:
            error_str = str(error_apertura)
            # Si se detecta "EOF marker not found", se intenta extraer imagenes con fitz
            if "EOF marker not found" in error_str:
                imagenes = extraer_imagenes_de_pdf(ruta_pdf)
                if imagenes:
                    temp_pdf = ruta_pdf + ".tmp"
                    crear_pdf_desde_imagenes(imagenes, temp_pdf)
                    os.replace(temp_pdf, ruta_pdf)
                    return ruta_pdf, imagenes, None
                else:
                    return None, [], f"Error al extraer imagenes: {error_str}"
            else:
                return None, [], f"Error al abrir PDF original: {error_str}"
        
        # Crear archivo temporal en el mismo directorio para la normalizacion
        temp_pdf = ruta_pdf + ".tmp"
        escritor_pdf = PdfWriter()
        try:
            for pagina in lector_pdf.pages:
                escritor_pdf.add_page(pagina)
            with open(temp_pdf, 'wb') as salida:
                escritor_pdf.write(salida)
        except Exception as error_escritura:
            return None, [], f"Error al escribir PDF normalizado: {str(error_escritura)}"
        
        # Extraer imagenes del PDF original
        imagenes = extraer_imagenes_de_pdf(ruta_pdf)
        # Crear PDF con imagenes extraidas en el archivo temporal
        crear_pdf_desde_imagenes(imagenes, temp_pdf)
        # Reemplazar el archivo original con el PDF normalizado
        os.replace(temp_pdf, ruta_pdf)
        return ruta_pdf, imagenes, None
    except Exception as e:
        return None, [], f"Error de normalizacion: {str(e)}"

def verificar_pdf(ruta_pdf, cadena_base64=None):
    """
    Verifica si el PDF es valido y, solo si es invalido, lo normaliza reemplazando el archivo original.

    Args:
        ruta_pdf (str): Ruta al archivo PDF
        cadena_base64 (str, opcional): Contenido PDF en base64

    Returns:
        tuple: (es_valido, mensaje, lista_imagenes)
    """
    if cadena_base64:
        es_valido_b64, datos_decod = verificar_base64(cadena_base64)
        if not es_valido_b64:
            return False, datos_decod, []
        temp_file = 'temp_file.pdf'
        with open(temp_file, 'wb') as f:
            f.write(datos_decod)
        ruta_pdf = temp_file

    if not ruta_pdf.lower().endswith('.pdf'):
        return False, "No es un archivo PDF.", []
    if os.path.getsize(ruta_pdf) == 0:
        return False, "Archivo vacio.", []

    try:
        # Si el PDF es valido, se retorna sin normalizar
        if verificar_formato_pdf(ruta_pdf):
            return True, "PDF valido.", []
        else:
            ruta_normalizada, lista_imagenes, error_norm = normalizar_pdf(ruta_pdf)
            if ruta_normalizada:
                return True, "PDF normalizado exitosamente.", lista_imagenes
            else:
                return False, "PDF no se pudo normalizar. Detalles: " + error_norm, []
    except Exception as e:
        return False, "Error inesperado al procesar PDF: " + str(e), []

def verificar_archivos_directorio(directorio):
    """
    Verifica todos los archivos en un directorio

    Args:
        directorio (str): Ruta al directorio

    Returns:
        tuple: (archivos_validos, archivos_invalidos)
    """
    archivos_validos = []
    archivos_invalidos = []
    for nombre in os.listdir(directorio):
        ruta_archivo = os.path.join(directorio, nombre)
        if os.path.isfile(ruta_archivo):
            es_valido, mensaje, imagenes = verificar_pdf(ruta_archivo)
            info_archivo = {
                "archivo": nombre,
                "mensaje": mensaje,
                "imagenes": imagenes
            }
            if es_valido:
                archivos_validos.append(info_archivo)
            else:
                archivos_invalidos.append(info_archivo)
    return archivos_validos, archivos_invalidos

@app.route('/api/verificar_archivo', methods=['POST'])
def api_verifica_archivo():
    """Endpoint API para verificar un archivo PDF individual"""
    datos = request.get_json()
    if not datos or 'archivo' not in datos:
        return jsonify({"error": "Se requiere la ruta del archivo"}), 400
    ruta_archivo = datos['archivo']
    if not os.path.exists(ruta_archivo):
        return jsonify({"error": f"El archivo {ruta_archivo} no existe"}), 404
    es_valido, mensaje, imagenes = verificar_pdf(ruta_archivo)
    return jsonify({
        "es_valido": es_valido,
        "mensaje": mensaje,
        "imagenes": imagenes
    })

@app.route('/api/verifica_base64', methods=['POST'])
def api_verifica_base64():
    """Endpoint API para verificar un PDF codificado en base64"""
    datos = request.get_json()
    if not datos or 'base64' not in datos:
        return jsonify({"error": "Se requiere un string base64"}), 400
    cadena_base64 = datos['base64']
    es_valido, mensaje, imagenes = verificar_pdf(None, cadena_base64)
    return jsonify({
        "es_valido": es_valido,
        "mensaje": mensaje,
        "imagenes": imagenes
    })

@app.route('/api/verifica_directorio', methods=['POST'])
def api_verifica_directorio():
    """Endpoint API para verificar todos los PDFs en un directorio"""
    datos = request.get_json()
    if not datos or 'directorio' not in datos:
        return jsonify({"error": "Se requiere la ruta del directorio"}), 400
    directorio = datos['directorio']
    if not os.path.exists(directorio) or not os.path.isdir(directorio):
        return jsonify({"error": f"El directorio {directorio} no existe o es invalido"}), 404
    archivos_validos, archivos_invalidos = verificar_archivos_directorio(directorio)
    return jsonify({
        "directorio": directorio,
        "archivos_validos": archivos_validos,
        "archivos_invalidos": archivos_invalidos
    })

@app.route('/', methods=['GET'])
def inicio():
    return '''
    <html>
        <head>
            <title>API de Verificacion de PDF</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
                h1 { color: #333; }
                h2 { color: #666; }
                pre { background: #f4f4f4; padding: 10px; border-radius: 5px; }
                code { background: #f4f4f4; padding: 2px 4px; border-radius: 3px; }
            </style>
        </head>
        <body>
            <h1>API de Verificacion de PDF</h1>
            <p>Esta API permite la verificacion y normalizacion de PDFs.</p>
            <h2>Endpoints</h2>
            <ul>
                <li><code>POST /api/verifica_archivo</code>: Verificar un archivo PDF individual</li>
                <li><code>POST /api/verifica_base64</code>: Verificar un PDF codificado en base64</li>
                <li><code>POST /api/verifica_directorio</code>: Verificar PDFs en un directorio</li>
            </ul>
        </body>
    </html>
    '''

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
