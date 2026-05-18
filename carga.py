import os
import sys
import csv
import json
import urllib.request
import urllib.error
from datetime import datetime

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLA = "ventas"

validated_carpeta = "data/validated"
logs_carpeta = "logs"
log_archivo = logs_carpeta + "/log_" + datetime.now().strftime("%Y%m%d") + ".txt"

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
        emitir("   CARGA FINALIZADA OK - duracion: " + ("%.2f" % duracion) + "s")
    else:
        emitir("   CARGA FINALIZADA CON ERROR - " + (motivo or "sin detalle"))
        emitir("   duracion parcial: " + ("%.2f" % duracion) + "s")
    emitir("================================================================")
    logfile.close()
    sys.exit(codigo)


def obtener_ultimo_validated():
    archivos = [f for f in os.listdir(validated_carpeta) if f.endswith(".csv")]
    if not archivos:
        return None
    archivos.sort()
    return os.path.join(validated_carpeta, archivos[-1])

def upsert_filas(filas):
    url = SUPABASE_URL + "/rest/v1/" + TABLA
    datos = json.dumps(filas).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=datos,
        method="POST",
        headers={
            "apikey": SUPABASE_KEY,
            "Authorization": "Bearer " + SUPABASE_KEY,
            "Content-Type": "application/json",
            "Prefer": "resolution=merge-duplicates,return=minimal"
        }
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, None
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")
    except Exception as e:
        return 0, str(e)


seccion("CARGA A BASE DE DATOS - PASO 4 DE 4")

subseccion("Parametros")
log("INFO", "destino             : Supabase (PostgreSQL)")
log("INFO", "tabla destino       : " + TABLA)
log("INFO", "estrategia          : upsert (merge-duplicates por id)")
log("INFO", "carpeta validados   : " + validated_carpeta)
log("INFO", "archivo de log      : " + log_archivo)

subseccion("Verificacion de credenciales")
if not SUPABASE_URL or not SUPABASE_KEY:
    log("ERROR", "faltan credenciales: SUPABASE_URL y/o SUPABASE_KEY no estan definidas")
    log("ERROR", "definirlas en .env / variables de entorno (ver .env.example)")
    cerrar(1, "credenciales ausentes")

url_segura = SUPABASE_URL.split("//")[-1][:30] + "..."
key_segura = SUPABASE_KEY[:8] + "..." + SUPABASE_KEY[-4:]
log("OK", "SUPABASE_URL detectada: " + url_segura)
log("OK", "SUPABASE_KEY detectada: " + key_segura + " (ofuscada)")

subseccion("Seleccion del archivo a cargar")
origen = obtener_ultimo_validated()
if not origen:
    log("ERROR", "no hay archivos en " + validated_carpeta + ". Ejecuta primero validacion.")
    cerrar(1, "no hay archivos validados")

log("OK", "archivo seleccionado: " + origen)
log("INFO", "tamano: " + str(os.path.getsize(origen)) + " bytes")

subseccion("Parseo del archivo")
filas = []
try:
    with open(origen, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            filas.append({
                "id": int(row["id"]),
                "fecha": row["fecha"],
                "producto": row["producto"],
                "categoria": row["categoria"],
                "cantidad": int(row["cantidad"]),
                "precio_unitario": int(row["precio_unitario"]),
                "vendedor": row["vendedor"],
                "region": row["region"]
            })
except Exception as e:
    log("ERROR", "no se pudo parsear el archivo: " + str(e))
    cerrar(1, "error de parseo")

log("OK", "registros parseados: " + str(len(filas)))

if not filas:
    log("ERROR", "no hay registros para cargar")
    cerrar(1, "archivo validado vacio")

subseccion("Insercion en Supabase")
BATCH = 50
total_lotes = (len(filas) + BATCH - 1) // BATCH
log("INFO", "tamano de lote: " + str(BATCH))
log("INFO", "lotes a procesar: " + str(total_lotes))
emitir("")

insertados = 0
errores = 0
detalles_error = []

for i in range(0, len(filas), BATCH):
    lote = filas[i:i + BATCH]
    n_lote = i // BATCH + 1
    log("INFO", "enviando lote " + str(n_lote) + "/" + str(total_lotes) + " (" + str(len(lote)) + " registros)...")
    status, error = upsert_filas(lote)
    if status in (200, 201):
        insertados += len(lote)
        log("OK", "lote " + str(n_lote) + " insertado - status HTTP " + str(status))
    else:
        errores += len(lote)
        msg = "lote " + str(n_lote) + " fallo - status " + str(status) + " - " + str(error)
        log("ERROR", msg)
        detalles_error.append(msg)

subseccion("Resumen de carga")
log("INFO", "registros enviados : " + str(len(filas)))
log("INFO", "insertados ok      : " + str(insertados))
log("INFO", "con error          : " + str(errores))

if errores > 0:
    log("ERROR", "la carga termino con errores - revisar permisos / RLS / esquema")
    for d in detalles_error:
        log("ERROR", "  " + d)
    cerrar(1, str(errores) + " registros fallaron")

cerrar(0)
