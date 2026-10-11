import ast
import csv
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo import MongoClient

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
ARCHIVO_PIXELES = BASE_DIR / "datos" / "pixeles_noaa_unicos_para_automatizacion.csv"
ARCHIVO_GEOJSON = BASE_DIR / "datos" / "areas_coralinas_pnn.geojson"

USUARIO = os.getenv("MONGO_INITDB_ROOT_USERNAME")
PASSWORD = os.getenv("MONGO_INITDB_ROOT_PASSWORD")
MONGO_HOST = os.getenv("MONGO_HOST", "mongodb")
MONGO_PORT = os.getenv("MONGO_PORT", "27017")
MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    if not USUARIO or not PASSWORD:
        raise RuntimeError(
            "Configure MONGO_URI o MONGO_INITDB_ROOT_USERNAME y "
            "MONGO_INITDB_ROOT_PASSWORD en el entorno."
        )
    MONGO_URI = (
        f"mongodb://{quote_plus(USUARIO)}:{quote_plus(PASSWORD)}"
        f"@{MONGO_HOST}:{MONGO_PORT}/?authSource=admin"
    )

app = FastAPI(
    title="API NOAA - Áreas Coralinas",
    description="API para consultar la exposición térmica de las áreas coralinas del PNN Corales del Rosario y de San Bernardo.",
    version="2.0.0",
)

cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://localhost:3000").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

cliente = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = cliente[os.getenv("MONGO_DATABASE", "proyecto_noaa")]
coleccion = db[os.getenv("MONGO_COLLECTION", "observaciones_noaa")]

pixeles_por_area = defaultdict(list)
with ARCHIVO_PIXELES.open("r", encoding="utf-8-sig", newline="") as archivo:
    for fila in csv.DictReader(archivo):
        pixel_id = fila["pixel_id"]
        for fid in ast.literal_eval(fila["fid_areas_coralinas"]):
            pixeles_por_area[int(fid)].append(pixel_id)


def cargar_geojson():
    with ARCHIVO_GEOJSON.open("r", encoding="utf-8") as archivo:
        return json.load(archivo)


GEOJSON = cargar_geojson()
FEATURES_POR_FID = {
    int(feature["properties"]["FID"]): feature
    for feature in GEOJSON["features"]
}


def obtener_fechas():
    return sorted(coleccion.distinct("fecha"))


def obtener_ultima_fecha():
    fechas = obtener_fechas()
    return fechas[-1] if fechas else None


def formatear_fecha(fecha):
    if fecha is None:
        return None
    return fecha.strftime("%Y-%m-%d %H:%M:%S")


def convertir_fecha(fecha):
    try:
        value = fecha.strip()
        if len(value) == 10:
            parsed = datetime.fromisoformat(value)
        else:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail="Formato de fecha inválido. Use YYYY-MM-DD o YYYY-MM-DD HH:MM:SS.",
        ) from error


def obtener_categoria(dhw):
    # Clasificación relativa del proyecto; no es una alerta oficial NOAA.
    if dhw < 3.57:
        return "Baja"
    if dhw < 4.74:
        return "Intermedia"
    return "Alta"


def obtener_areas_por_fecha(fecha=None):
    fecha_datetime = convertir_fecha(fecha) if fecha else obtener_ultima_fecha()
    if fecha_datetime is None:
        return []

    pipeline = [
        {"$match": {"fecha": fecha_datetime}},
        {
            "$group": {
                "_id": "$pixel_id",
                "latitud": {"$first": "$latitud"},
                "longitud_wgs84": {"$first": "$longitud_wgs84"},
                "dhw": {"$avg": "$dhw"},
                "sst": {"$avg": "$sst"},
                "ssta": {"$avg": "$ssta"},
                "hotspot": {"$avg": "$hotspot"},
                "fecha_inicial": {"$min": "$fecha"},
                "fecha_final": {"$max": "$fecha"},
            }
        },
    ]

    datos_pixel = {
        documento["_id"]: documento
        for documento in coleccion.aggregate(pipeline)
    }

    resultados = []
    for fid, pixeles in sorted(pixeles_por_area.items()):
        registros = [datos_pixel[pixel] for pixel in pixeles if pixel in datos_pixel]
        if not registros:
            continue

        dhw_promedio = round(sum(r["dhw"] for r in registros) / len(registros), 2)
        resultados.append(
            {
                "fid_area_coralina": fid,
                "numero_pixeles": len(registros),
                "dhw_promedio": dhw_promedio,
                "dhw_max_asociado": round(max(r["dhw"] for r in registros), 2),
                "sst_promedio": round(sum(r["sst"] for r in registros) / len(registros), 2),
                "ssta_promedio": round(sum(r["ssta"] for r in registros) / len(registros), 2),
                "hotspot_promedio": round(sum(r["hotspot"] for r in registros) / len(registros), 2),
                "categoria_exposicion_relativa": obtener_categoria(dhw_promedio),
                "fecha": formatear_fecha(fecha_datetime),
                "fecha_inicial": formatear_fecha(min(r["fecha_inicial"] for r in registros)),
                "fecha_final": formatear_fecha(max(r["fecha_final"] for r in registros)),
            }
        )

    return resultados


@app.get("/health")
def health():
    try:
        cliente.admin.command("ping")
        return {"estado": "ok", "mongodb": "conectado"}
    except Exception as error:
        return JSONResponse(
            status_code=503,
            content={"estado": "error", "mongodb": "no disponible", "detalle": str(error)},
        )


@app.get("/fechas")
def fechas_disponibles():
    fechas_datetime = obtener_fechas()
    fechas = [formatear_fecha(fecha) for fecha in fechas_datetime]
    return {
        "total_fechas": len(fechas),
        "fecha_inicial": fechas[0] if fechas else None,
        "fecha_final": fechas[-1] if fechas else None,
        "fechas": fechas,
    }


@app.get("/geojson")
def geojson():
    return GEOJSON


@app.get("/resumen")
def resumen():
    fechas = obtener_fechas()
    areas_actuales = obtener_areas_por_fecha()
    counts = {"Baja": 0, "Intermedia": 0, "Alta": 0}
    for area_item in areas_actuales:
        counts[area_item["categoria_exposicion_relativa"]] = counts.get(area_item["categoria_exposicion_relativa"], 0) + 1

    if areas_actuales:
        total = len(areas_actuales)
        promedio = {
            "dhw": round(sum(a["dhw_promedio"] for a in areas_actuales) / total, 2),
            "sst": round(sum(a["sst_promedio"] for a in areas_actuales) / total, 2),
            "ssta": round(sum(a["ssta_promedio"] for a in areas_actuales) / total, 2),
            "hotspot": round(sum(a["hotspot_promedio"] for a in areas_actuales) / total, 2),
        }
        dhw_max = round(max(a["dhw_max_asociado"] for a in areas_actuales), 2)
    else:
        promedio = {"dhw": 0, "sst": 0, "ssta": 0, "hotspot": 0}
        dhw_max = 0

    total_pixeles = len(coleccion.distinct("pixel_id"))
    return {
        "total_areas": len(pixeles_por_area),
        "areas_con_datos": len(areas_actuales),
        "total_pixeles": total_pixeles,
        "total_fechas": len(fechas),
        "fecha_final": formatear_fecha(fechas[-1]) if fechas else None,
        "fecha_inicial": formatear_fecha(fechas[0]) if fechas else None,
        "clasificacion": counts,
        "promedios": promedio,
        "dhw_max": dhw_max,
    }


@app.get("/areas")
def areas(
    fecha: str | None = Query(default=None, description="Fecha exacta: YYYY-MM-DD o YYYY-MM-DD HH:MM:SS")
):
    if fecha is not None:
        fecha_datetime = convertir_fecha(fecha)
        if fecha_datetime not in obtener_fechas():
            raise HTTPException(status_code=404, detail=f"No existe la fecha {fecha} en MongoDB.")
    resultados = obtener_areas_por_fecha(fecha)
    fecha_resultado = convertir_fecha(fecha) if fecha else obtener_ultima_fecha()
    return {
        "fecha_consultada": formatear_fecha(fecha_resultado),
        "total_areas": len(resultados),
        "areas": resultados,
    }


@app.get("/areas/{fid}")
def area(fid: int):
    fecha = obtener_ultima_fecha()
    resultados = obtener_areas_por_fecha()
    resultado = next((fila for fila in resultados if fila["fid_area_coralina"] == fid), None)
    if resultado is None:
        raise HTTPException(status_code=404, detail=f"No se encontró el área con FID {fid}.")
    resultado["fecha"] = formatear_fecha(fecha)
    return resultado


@app.get("/areas/{fid}/historico")
def historico_area(fid: int):
    if fid not in pixeles_por_area:
        raise HTTPException(status_code=404, detail=f"No se encontró el área con FID {fid}.")

    historico = []
    for fecha_datetime in obtener_fechas():
        resultados = obtener_areas_por_fecha(formatear_fecha(fecha_datetime))
        resultado = next((fila for fila in resultados if fila["fid_area_coralina"] == fid), None)
        if resultado:
            historico.append(resultado)

    return {
        "fid_area_coralina": fid,
        "total_registros": len(historico),
        "historico": historico,
    }



@app.post("/chat")
def chat_coral(payload: dict = Body(...)):
    webhook_url = os.getenv("MAKE_CHAT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        raise HTTPException(
            status_code=503,
            detail="El chat todavía no está configurado. Falta MAKE_CHAT_WEBHOOK_URL en el entorno del backend.",
        )

    mensaje = str(payload.get("message", "")).strip()
    if not mensaje:
        raise HTTPException(status_code=400, detail="Escribe una pregunta para Coral.")
    if len(mensaje) > 1500:
        raise HTTPException(status_code=400, detail="La pregunta no puede superar los 1500 caracteres.")

    fecha_solicitada = payload.get("fecha")
    if fecha_solicitada:
        fecha_datetime = convertir_fecha(str(fecha_solicitada))
        if fecha_datetime not in obtener_fechas():
            raise HTTPException(status_code=404, detail=f"No hay datos para la fecha {fecha_solicitada}.")
        fecha_contexto = formatear_fecha(fecha_datetime)
    else:
        fecha_contexto = formatear_fecha(obtener_ultima_fecha())

    datos_areas = obtener_areas_por_fecha(fecha_contexto) if fecha_contexto else []
    conteo = {"Baja": 0, "Intermedia": 0, "Alta": 0}
    for item in datos_areas:
        categoria = item["categoria_exposicion_relativa"]
        conteo[categoria] = conteo.get(categoria, 0) + 1

    contexto = {
        "fecha_consultada": fecha_contexto,
        "total_areas_con_datos": len(datos_areas),
        "clasificacion_exposicion_relativa": conteo,
        "areas": [
            {
                "fid": item["fid_area_coralina"],
                "dhw_promedio": item["dhw_promedio"],
                "dhw_max_asociado": item["dhw_max_asociado"],
                "sst_promedio": item["sst_promedio"],
                "ssta_promedio": item["ssta_promedio"],
                "hotspot_promedio": item["hotspot_promedio"],
                "categoria": item["categoria_exposicion_relativa"],
            }
            for item in datos_areas
        ],
        "nota": "Baja, Intermedia y Alta son categorías relativas internas del proyecto, no alertas oficiales NOAA."
    }

    solicitud_make = {
        "request": (
            "Pregunta del usuario: " + mensaje
            + "\\n\\nContexto actual verificado de Coraleum (JSON): "
            + json.dumps(contexto, ensure_ascii=False)
            + "\\n\\nResponde en español claro. Usa el contexto para preguntas sobre datos actuales. "
            "Si la información no está en el contexto, dilo y no inventes valores."
        ),
        "conversationID": str(payload.get("conversation_id") or "coraleum-web"),
        "source": "coraleum-web",
    }

    headers = {"Content-Type": "application/json"}
    api_key = os.getenv("MAKE_CHAT_API_KEY", "").strip()
    if api_key:
        headers["x-make-apikey"] = api_key

    request = Request(
        webhook_url,
        data=json.dumps(solicitud_make, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with urlopen(request, timeout=45) as response:
            respuesta_make = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        raise HTTPException(status_code=502, detail=f"Make devolvió el estado HTTP {error.code}.") from error
    except (URLError, TimeoutError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=502, detail="No fue posible obtener respuesta del escenario de Make.") from error

    respuesta = (
        respuesta_make.get("response")
        or respuesta_make.get("reply")
        or respuesta_make.get("message")
    ) if isinstance(respuesta_make, dict) else None
    if not respuesta and isinstance(respuesta_make, str):
        respuesta = respuesta_make
    if not respuesta:
        raise HTTPException(
            status_code=502,
            detail="Make respondió, pero no se encontró el campo 'response'. Revisa el módulo Webhook response.",
        )

    return {"reply": str(respuesta), "fecha_consultada": fecha_contexto}
