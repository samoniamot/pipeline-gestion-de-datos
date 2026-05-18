import os
import sys
import shutil
import csv
from datetime import datetime

origen = "origen/ventas.csv"
destino_carpeta = "data/raw"
logs_carpeta = "logs"
fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
destino = destino_carpeta + "/ventas_raw_" + fecha + ".csv"
log_archivo = logs_carpeta + "/log_" + datetime.now().strftime("%Y%m%d") + ".txt"

os.makedirs(destino_carpeta, exist_ok=True)
os.makedirs(logs_carpeta, exist_ok=True)

logfile = open(log_archivo, "a")
inicio_etapa = datetime.now()

def emitir(texto):
    print(texto, flush=True)
    logfile.write(texto + "\n")

def log(nivel, texto):
    hora = datetime.now().strftime("%H:%M:%S")
    emitir("[" + nivel.ljust(5) + "] " + hora + "  " + texto)

def seccion(titulo):
    emitir("")
    emitir("================================================================")
    emitir("   " + titulo)
    emitir("   " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    emitir("================================================================")

def subseccion(titulo):
    emitir("")
    emitir("------ " + titulo + " ------")

def cerrar(codigo=0, motivo=None):
    duracion = (datetime.now() - inicio_etapa).total_seconds()
    emitir("")
    emitir("================================================================")
    if codigo == 0:
        emitir("   INGESTA FINALIZADA OK - duracion: " + ("%.2f" % duracion) + "s")
    else:
        emitir("   INGESTA FINALIZADA CON ERROR - " + (motivo or "sin detalle"))
        emitir("   duracion parcial: " + ("%.2f" % duracion) + "s")
    emitir("================================================================")
    logfile.close()
    sys.exit(codigo)


seccion("INGESTA - PASO 1 DE 4")

subseccion("Parametros")
log("INFO", "archivo origen   : " + origen)
log("INFO", "carpeta destino  : " + destino_carpeta)
log("INFO", "archivo destino  : " + destino)
log("INFO", "archivo de log   : " + log_archivo)

subseccion("Verificacion de origen")
if not os.path.exists(origen):
    log("ERROR", "no existe el archivo de origen: " + origen)
    cerrar(1, "archivo origen no encontrado")

tamano_bytes = os.path.getsize(origen)
log("OK", "archivo origen encontrado (" + str(tamano_bytes) + " bytes)")

subseccion("Lectura del CSV")
total = 0
columnas_detectadas = []
muestra = None
try:
    with open(origen, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        columnas_detectadas = next(reader)
        for row in reader:
            total += 1
            if muestra is None:
                muestra = row
except Exception as e:
    log("ERROR", "no se pudo leer el CSV: " + str(e))
    cerrar(1, "error de lectura del CSV")

log("INFO", "columnas detectadas (" + str(len(columnas_detectadas)) + "): " + ", ".join(columnas_detectadas))
log("INFO", "registros encontrados: " + str(total))
if muestra:
    log("INFO", "muestra primera fila: " + " | ".join(muestra))

if total == 0:
    log("ERROR", "el archivo no contiene registros")
    cerrar(1, "archivo origen vacio")

subseccion("Copia con timestamp")
try:
    shutil.copy(origen, destino)
except Exception as e:
    log("ERROR", "no se pudo copiar el archivo: " + str(e))
    cerrar(1, "error al copiar archivo")

tamano_destino = os.path.getsize(destino)
log("OK", "archivo copiado a: " + destino)
log("OK", "tamano destino: " + str(tamano_destino) + " bytes")

subseccion("Resumen")
log("OK", "registros ingestados: " + str(total))
log("OK", "trazabilidad: archivo timestampeado en data/raw/")

cerrar(0)
