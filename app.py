import os
import json
import subprocess
import urllib.request
import urllib.error
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, stream_with_context

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TABLA = "ventas"

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "Faltan credenciales. Defina SUPABASE_URL y SUPABASE_KEY como variables de entorno "
        "(ver .env.example). Por seguridad, las credenciales no se almacenan en el codigo fuente."
    )

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Content-Type": "application/json"
}

# ---------------------------------------------------------------------------
# Utilidades Supabase
# ---------------------------------------------------------------------------

def sb_request(method, path, data=None, extra_headers=None):
    url = SUPABASE_URL + "/rest/v1/" + path
    body = json.dumps(data).encode("utf-8") if data is not None else None
    headers = dict(HEADERS)
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

def get_ventas(orden="id"):
    status, data = sb_request("GET", TABLA + "?select=*&order=" + orden)
    if status == 200:
        return data
    return []

def insert_venta(venta):
    status, data = sb_request("POST", TABLA, data=venta,
                               extra_headers={"Prefer": "return=representation"})
    return status, data

def update_venta(id_venta, campos):
    status, data = sb_request("PATCH", TABLA + "?id=eq." + str(id_venta), data=campos,
                               extra_headers={"Prefer": "return=representation"})
    return status, data

def delete_venta(id_venta):
    status, data = sb_request("DELETE", TABLA + "?id=eq." + str(id_venta))
    return status, data


# carpetas de la pipeline
def contar_archivos(carpeta):
    ruta = os.path.join(BASE_DIR, carpeta)
    if not os.path.exists(ruta):
        return 0
    return len([f for f in os.listdir(ruta) if f.endswith(".csv")])

def estado_pipeline():
    return {
        "raw":       contar_archivos("data/raw"),
        "processed": contar_archivos("data/processed"),
        "validated": contar_archivos("data/validated"),
        "invalid":   contar_archivos("data/invalid"),
    }

def leer_log():
    log_path = os.path.join(BASE_DIR, "logs", "log_" + datetime.now().strftime("%Y%m%d") + ".txt")
    if not os.path.exists(log_path):
        return "(sin log de hoy)"
    with open(log_path, "r", encoding="utf-8") as f:
        lineas = f.readlines()
    return "".join(lineas[-60:])

# rutas
@app.route("/")
def index():
    ventas = get_ventas()
    pipeline = estado_pipeline()
    log = leer_log()
    return render_template("index.html", ventas=ventas, pipeline=pipeline, log=log)

SCRIPTS = {
    "ingesta":    "ingesta.py",
    "limpieza":   "limpieza.py",
    "validacion": "validacion.py",
    "carga":      "carga.py",
}

ETAPAS_ORDEN = [
    ("ingesta",    "Paso 1 - Ingesta"),
    ("limpieza",   "Paso 2 - Limpieza"),
    ("validacion", "Paso 3 - Validacion"),
    ("carga",      "Paso 4 - Carga a base de datos"),
]

@app.route("/ejecutar/<etapa>", methods=["POST"])
def ejecutar(etapa):
    if etapa not in SCRIPTS:
        return jsonify({"ok": False, "salida": "etapa desconocida"}), 400

    try:
        resultado = subprocess.run(
            ["python3", os.path.join(BASE_DIR, SCRIPTS[etapa])],
            capture_output=True,
            text=True,
            cwd=BASE_DIR
        )
        salida = resultado.stdout + resultado.stderr
        return jsonify({"ok": resultado.returncode == 0, "salida": salida})
    except Exception as e:
        return jsonify({"ok": False, "salida": "Error al ejecutar: " + str(e)})


@app.route("/ejecutar_todo", methods=["POST"])
def ejecutar_todo():
    def generar():
        inicio_total = datetime.now()
        yield "================================================\n"
        yield " EJECUCION COMPLETA DE PIPELINE\n"
        yield " Inicio: " + inicio_total.strftime("%Y-%m-%d %H:%M:%S") + "\n"
        yield "================================================\n\n"

        for clave, titulo in ETAPAS_ORDEN:
            yield "----- " + titulo + " -----\n"
            inicio = datetime.now()
            try:
                proc = subprocess.Popen(
                    ["python3", "-u", os.path.join(BASE_DIR, SCRIPTS[clave])],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=BASE_DIR,
                    bufsize=1
                )
                for linea in proc.stdout:
                    yield linea
                proc.wait()
                duracion = (datetime.now() - inicio).total_seconds()

                if proc.returncode != 0:
                    yield "\n[ERROR] " + titulo + " fallo con codigo " + str(proc.returncode) + "\n"
                    yield "[ABORTADO] Pipeline detenida. Los pasos posteriores NO se ejecutaron.\n"
                    yield "Duracion parcial: " + ("%.2f" % duracion) + "s\n"
                    return

                yield "[OK] " + titulo + " completado en " + ("%.2f" % duracion) + "s\n\n"
            except Exception as e:
                yield "\n[ERROR] Excepcion ejecutando " + titulo + ": " + str(e) + "\n"
                yield "[ABORTADO] Pipeline detenida.\n"
                return

        duracion_total = (datetime.now() - inicio_total).total_seconds()
        yield "================================================\n"
        yield " PIPELINE COMPLETA - TODOS LOS PASOS OK\n"
        yield " Duracion total: " + ("%.2f" % duracion_total) + "s\n"
        yield "================================================\n"

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
    }
    return Response(stream_with_context(generar()), mimetype="text/plain", headers=headers)

# crud en ventas


@app.route("/ventas/agregar", methods=["POST"])
def agregar():
    venta = {
        "id":              int(request.form["id"]),
        "fecha":           request.form["fecha"],
        "producto":        request.form["producto"].strip().title(),
        "categoria":       request.form["categoria"].strip().title(),
        "cantidad":        int(request.form["cantidad"]),
        "precio_unitario": int(request.form["precio_unitario"]),
        "vendedor":        request.form["vendedor"].strip().title(),
        "region":          request.form["region"].strip().title(),
    }
    insert_venta(venta)
    return redirect(url_for("index"))

@app.route("/ventas/editar/<int:id_venta>", methods=["POST"])
def editar(id_venta):
    campos = {
        "fecha":           request.form["fecha"],
        "producto":        request.form["producto"].strip().title(),
        "categoria":       request.form["categoria"].strip().title(),
        "cantidad":        int(request.form["cantidad"]),
        "precio_unitario": int(request.form["precio_unitario"]),
        "vendedor":        request.form["vendedor"].strip().title(),
        "region":          request.form["region"].strip().title(),
    }
    update_venta(id_venta, campos)
    return redirect(url_for("index"))

@app.route("/ventas/eliminar/<int:id_venta>", methods=["POST"])
def eliminar(id_venta):
    delete_venta(id_venta)
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, port=5000)
