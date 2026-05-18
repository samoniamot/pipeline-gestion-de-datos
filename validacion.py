import os
import sys
import csv
from datetime import datetime

processed_carpeta = "data/processed"
validated_carpeta = "data/validated"
invalid_carpeta = "data/invalid"
logs_carpeta = "logs"
log_archivo = logs_carpeta + "/log_" + datetime.now().strftime("%Y%m%d") + ".txt"

os.makedirs(validated_carpeta, exist_ok=True)
os.makedirs(invalid_carpeta, exist_ok=True)
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
        emitir("   VALIDACION FINALIZADA OK - duracion: " + ("%.2f" % duracion) + "s")
    else:
        emitir("   VALIDACION FINALIZADA CON ERROR - " + (motivo or "sin detalle"))
        emitir("   duracion parcial: " + ("%.2f" % duracion) + "s")
    emitir("================================================================")
    logfile.close()
    sys.exit(codigo)


def obtener_ultimo_processed():
    archivos = [f for f in os.listdir(processed_carpeta) if f.endswith(".csv")]
    if not archivos:
        return None
    archivos.sort()
    return os.path.join(processed_carpeta, archivos[-1])

HOY = datetime.now().date()
COLUMNAS = ["id", "fecha", "producto", "categoria", "cantidad", "precio_unitario", "vendedor", "region"]

def validar_fila(row):
    errores = []

    try:
        int(row["id"])
    except (ValueError, KeyError):
        errores.append("id no es entero")

    try:
        cantidad = int(row["cantidad"])
    except (ValueError, KeyError):
        errores.append("cantidad no es entero")
        cantidad = None

    try:
        precio = int(row["precio_unitario"])
    except (ValueError, KeyError):
        errores.append("precio_unitario no es entero")
        precio = None

    try:
        fecha = datetime.strptime(row["fecha"], "%Y-%m-%d").date()
    except (ValueError, KeyError):
        errores.append("fecha no tiene formato YYYY-MM-DD")
        fecha = None

    if fecha and fecha > HOY:
        errores.append("fecha futura: " + row["fecha"])

    if cantidad is not None and cantidad <= 0:
        errores.append("cantidad debe ser mayor a 0")

    if precio is not None and precio <= 0:
        errores.append("precio_unitario debe ser mayor a 0")

    if not row.get("producto", "").strip():
        errores.append("producto vacio")

    if not row.get("vendedor", "").strip():
        errores.append("vendedor vacio")

    if not row.get("region", "").strip():
        errores.append("region vacia")

    return errores


seccion("VALIDACION - PASO 3 DE 4")

subseccion("Parametros")
log("INFO", "carpeta origen        : " + processed_carpeta)
log("INFO", "carpeta validos       : " + validated_carpeta)
log("INFO", "carpeta invalidos     : " + invalid_carpeta)
log("INFO", "fecha actual (HOY)    : " + HOY.strftime("%Y-%m-%d"))
log("INFO", "archivo de log        : " + log_archivo)

subseccion("Seleccion del archivo a validar")
origen = obtener_ultimo_processed()
if not origen:
    log("ERROR", "no hay archivos en " + processed_carpeta + ". Ejecuta primero limpieza.")
    cerrar(1, "no hay archivos procesados")

log("OK", "archivo seleccionado: " + origen)
log("INFO", "tamano: " + str(os.path.getsize(origen)) + " bytes")

fecha_proceso = datetime.now().strftime("%Y%m%d_%H%M%S")
destino_validos = validated_carpeta + "/ventas_validated_" + fecha_proceso + ".csv"
destino_invalidos = invalid_carpeta + "/ventas_invalid_" + fecha_proceso + ".csv"

subseccion("Reglas de validacion")
log("INFO", "Estructurales:")
log("INFO", "  - id, cantidad, precio_unitario deben ser enteros")
log("INFO", "  - fecha en formato YYYY-MM-DD")
log("INFO", "Semanticas:")
log("INFO", "  - fecha no puede ser futura (> " + HOY.strftime("%Y-%m-%d") + ")")
log("INFO", "  - cantidad > 0")
log("INFO", "  - precio_unitario > 0")
log("INFO", "  - producto, vendedor, region no vacios")

subseccion("Validacion fila por fila")

filas_leidas = 0
filas_validas = 0
filas_invalidas = 0
validos = []
invalidos = []
contador_errores = {}

COLUMNAS_INVALIDOS = COLUMNAS + ["errores"]

try:
    with open(origen, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas_leidas += 1
            errores = validar_fila(row)
            if errores:
                row_invalido = dict(row)
                row_invalido["errores"] = " | ".join(errores)
                invalidos.append(row_invalido)
                for err in errores:
                    clave_err = err.split(":")[0].strip()
                    contador_errores[clave_err] = contador_errores.get(clave_err, 0) + 1
                log("WARN", "fila " + str(filas_leidas) + " invalida - " + " | ".join(errores))
                filas_invalidas += 1
            else:
                validos.append(row)
                filas_validas += 1
except Exception as e:
    log("ERROR", "error procesando el archivo: " + str(e))
    cerrar(1, "excepcion en validacion")

subseccion("Escritura de archivos de salida")
try:
    with open(destino_validos, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS)
        writer.writeheader()
        writer.writerows(validos)
    log("OK", "validos guardados   : " + destino_validos + " (" + str(len(validos)) + " filas)")
except Exception as e:
    log("ERROR", "no se pudo escribir validos: " + str(e))
    cerrar(1, "error escribiendo validos")

try:
    with open(destino_invalidos, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNAS_INVALIDOS)
        writer.writeheader()
        writer.writerows(invalidos)
    log("OK", "invalidos guardados : " + destino_invalidos + " (" + str(len(invalidos)) + " filas)")
except Exception as e:
    log("ERROR", "no se pudo escribir invalidos: " + str(e))
    cerrar(1, "error escribiendo invalidos")

subseccion("Resumen de validacion")
log("INFO", "filas leidas    : " + str(filas_leidas))
log("INFO", "filas validas   : " + str(filas_validas))
log("INFO", "filas invalidas : " + str(filas_invalidas))
if contador_errores:
    log("INFO", "desglose de errores detectados:")
    for err, cnt in sorted(contador_errores.items(), key=lambda x: -x[1]):
        log("INFO", "  - " + err + ": " + str(cnt))

if filas_validas == 0:
    log("ERROR", "no quedaron filas validas - la carga no podra ejecutarse")
    cerrar(1, "0 filas validas")

cerrar(0)
