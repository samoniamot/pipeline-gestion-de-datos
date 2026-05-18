import os
import sys
import csv
from datetime import datetime

raw_carpeta = "data/raw"
processed_carpeta = "data/processed"
logs_carpeta = "logs"
log_archivo = logs_carpeta + "/log_" + datetime.now().strftime("%Y%m%d") + ".txt"

os.makedirs(processed_carpeta, exist_ok=True)
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
        emitir("   LIMPIEZA FINALIZADA OK - duracion: " + ("%.2f" % duracion) + "s")
    else:
        emitir("   LIMPIEZA FINALIZADA CON ERROR - " + (motivo or "sin detalle"))
        emitir("   duracion parcial: " + ("%.2f" % duracion) + "s")
    emitir("================================================================")
    logfile.close()
    sys.exit(codigo)


def normalizar_fecha(fecha_str):
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(fecha_str.strip(), fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None

def obtener_ultimo_raw():
    archivos = [f for f in os.listdir(raw_carpeta) if f.endswith(".csv")]
    if not archivos:
        return None
    archivos.sort()
    return os.path.join(raw_carpeta, archivos[-1])


seccion("LIMPIEZA - PASO 2 DE 4")

subseccion("Parametros")
log("INFO", "carpeta origen   : " + raw_carpeta)
log("INFO", "carpeta destino  : " + processed_carpeta)
log("INFO", "archivo de log   : " + log_archivo)

subseccion("Seleccion del archivo a limpiar")
origen = obtener_ultimo_raw()
if not origen:
    log("ERROR", "no hay archivos en " + raw_carpeta + ". Ejecuta primero ingesta.")
    cerrar(1, "no hay archivos raw")

log("OK", "archivo seleccionado: " + origen)
log("INFO", "tamano: " + str(os.path.getsize(origen)) + " bytes")

fecha_proceso = datetime.now().strftime("%Y%m%d_%H%M%S")
destino = processed_carpeta + "/ventas_processed_" + fecha_proceso + ".csv"

columnas = ["id", "fecha", "producto", "categoria", "cantidad", "precio_unitario", "vendedor", "region"]
log("INFO", "columnas esperadas: " + ", ".join(columnas))

subseccion("Procesamiento fila por fila")
log("INFO", "reglas aplicadas:")
log("INFO", "  - trim de espacios en blanco")
log("INFO", "  - descarte si algun campo obligatorio esta vacio")
log("INFO", "  - title case en producto/categoria/vendedor/region")
log("INFO", "  - normalizacion de fecha a formato YYYY-MM-DD")
log("INFO", "  - eliminacion de duplicados por ID")
emitir("")

filas_leidas = 0
filas_limpias = 0
filas_descartadas = 0
descartes_por_vacio = 0
descartes_por_fecha = 0
descartes_por_duplicado = 0
duplicados = set()
filas_salida = []

try:
    with open(origen, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas_leidas += 1

            row = {k: v.strip() for k, v in row.items()}

            if any(row.get(col, "") == "" for col in columnas):
                log("WARN", "fila " + str(filas_leidas) + " descartada - campos vacios")
                filas_descartadas += 1
                descartes_por_vacio += 1
                continue

            row["producto"] = row["producto"].title()
            row["categoria"] = row["categoria"].title()
            row["vendedor"] = row["vendedor"].title()
            row["region"] = row["region"].title()

            fecha_norm = normalizar_fecha(row["fecha"])
            if not fecha_norm:
                log("WARN", "fila " + str(filas_leidas) + " descartada - fecha invalida: " + row["fecha"])
                filas_descartadas += 1
                descartes_por_fecha += 1
                continue
            row["fecha"] = fecha_norm

            row_id = row["id"]
            if row_id in duplicados:
                log("WARN", "fila " + str(filas_leidas) + " descartada - duplicado id: " + row_id)
                filas_descartadas += 1
                descartes_por_duplicado += 1
                continue
            duplicados.add(row_id)

            filas_limpias += 1
            filas_salida.append(row)
except Exception as e:
    log("ERROR", "error procesando el archivo: " + str(e))
    cerrar(1, "excepcion en procesamiento")

subseccion("Escritura de archivo procesado")
try:
    with open(destino, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columnas)
        writer.writeheader()
        writer.writerows(filas_salida)
except Exception as e:
    log("ERROR", "no se pudo escribir el archivo procesado: " + str(e))
    cerrar(1, "error de escritura")

log("OK", "archivo guardado: " + destino)
log("OK", "tamano destino: " + str(os.path.getsize(destino)) + " bytes")

subseccion("Resumen")
log("INFO", "filas leidas         : " + str(filas_leidas))
log("INFO", "filas limpias        : " + str(filas_limpias))
log("INFO", "filas descartadas    : " + str(filas_descartadas))
log("INFO", "  por campos vacios  : " + str(descartes_por_vacio))
log("INFO", "  por fecha invalida : " + str(descartes_por_fecha))
log("INFO", "  por duplicado id   : " + str(descartes_por_duplicado))

if filas_limpias == 0:
    log("ERROR", "no quedaron filas validas tras la limpieza")
    cerrar(1, "0 filas tras limpieza")

cerrar(0)
