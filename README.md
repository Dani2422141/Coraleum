# Coraleum — Explorador de Estrés Térmico en Corales

Aplicación para consultar datos NOAA Coral Reef Watch asociados a las 47 áreas coralinas del PNN Corales del Rosario y de San Bernardo.

## Arquitectura actual

```text
                  NOAA / datos históricos
                           │
                           ▼
                       MongoDB
                    (contenedor Docker)
                           │
                           ▼
                    FastAPI / Python
                       puerto 8000
                           │
                           ▼
                 Nginx + React / Vite
                       puerto 3000
```

El frontend ya no contiene datos térmicos de prueba. Consulta la API y la API consulta MongoDB.

La geometría del mapa proviene de `datos/areas_coralinas_pnn.geojson`, por lo que los polígonos se dibujan con la forma geográfica real del archivo, en lugar de usar puntos `mapX/mapY` inventados.

> El GeoJSON incluido solamente tiene `FID` y `ETIQUETA`; por eso la interfaz identifica las áreas mediante su FID. No se inventaron nombres de áreas que no existan en los datos fuente.

## Cambios principales

- Frontend convertido de TypeScript/TSX a JavaScript/JSX.
- React + Vite mantenidos como stack del frontend.
- Datos térmicos obtenidos desde MongoDB mediante FastAPI.
- Fechas disponibles obtenidas desde `/api/fechas`.
- Áreas obtenidas desde `/api/areas?fecha=...`.
- Histórico obtenido desde `/api/areas/{fid}/historico`.
- Resumen territorial obtenido desde `/api/resumen`.
- GeoJSON obtenido desde `/api/geojson`.
- Mapa SVG basado en los polígonos reales del GeoJSON.
- Backend dockerizado y conectado al servicio MongoDB mediante el hostname `mongodb` de Docker Compose.
- Frontend Nginx configurado para hacer proxy de `/api/*` hacia FastAPI.
- En desarrollo con Vite, `/api/*` se proxifica a `http://localhost:8000`.

## 1. Configurar variables de entorno

Copia `.env.example` como `.env` y define tus credenciales:

```env
MONGO_INITDB_ROOT_USERNAME=tu_usuario
MONGO_INITDB_ROOT_PASSWORD=tu_contraseña
```

No subas `.env` al repositorio.

## 2. Levantar todo con Docker

Desde la raíz del proyecto:

```bash
docker compose up -d --build
```

Esto levanta:

| Servicio | Puerto local | Uso |
|---|---:|---|
| `mongodb` | `27017` | Base de datos |
| `backend` | `8000` | FastAPI |
| `frontend` | `3000` | React servido por Nginx |

Abre:

```text
http://localhost:3000
```

La API también queda disponible en:

```text
http://localhost:8000/docs
```

Y puedes comprobar la conexión con:

```text
http://localhost:8000/health
```

## 3. Conexión frontend → backend cuando ambos están dockerizados

El navegador entra a `http://localhost:3000`.

El frontend solicita, por ejemplo:

```text
/api/areas?fecha=2026-09-03%2012:00:00
```

Nginx recibe esa solicitud y la reenvía internamente a:

```text
http://backend:8000/areas?fecha=2026-09-03%2012:00:00
```

`backend` es el nombre del servicio Docker y funciona porque ambos servicios están en la misma red creada por Docker Compose.

Esto evita poner `localhost:8000` dentro del código del navegador cuando el frontend está dentro de Docker.

## 4. Desarrollo del frontend fuera de Docker

Puedes levantar solamente MongoDB + backend:

```bash
docker compose up -d mongodb backend
```

Luego, dentro de `frontend/`:

```bash
npm install
npm run dev
```

Vite escucha en `http://localhost:5173` y tiene configurado un proxy:

```text
/api/* → http://localhost:8000/*
```

Por lo tanto el código React sigue usando `/api/...` y no necesitas cambiar URLs entre desarrollo y producción.

## 5. Migración de datos a MongoDB

Si MongoDB todavía no tiene las observaciones, ejecuta tu proceso de migración desde la raíz del proyecto. Para scripts que se ejecutan en el host, `localhost:27017` es correcto porque Docker publica ese puerto.

Por ejemplo, revisa los scripts existentes en `scripts/` y ejecuta el de migración que corresponda a tu flujo de datos.

Si el script se ejecutara dentro de un contenedor, en cambio, debe usar `mongodb:27017`, no `localhost:27017`.

## 6. Endpoints usados por React

### `GET /fechas`

Devuelve las fechas existentes en MongoDB.

### `GET /areas?fecha=YYYY-MM-DD HH:MM:SS`

Devuelve el estado térmico de las áreas para una fecha concreta.

### `GET /areas/{fid}`

Devuelve la información actual de un área.

### `GET /areas/{fid}/historico`

Devuelve la serie histórica de esa área.

### `GET /resumen`

Calcula los KPIs territoriales directamente a partir de MongoDB.

### `GET /geojson`

Devuelve la geometría real de las 47 áreas coralinas.

### `GET /health`

Comprueba la conexión con MongoDB.

## Nota sobre la clasificación

`Baja`, `Intermedia` y `Alta` siguen siendo la clasificación relativa que ya utilizaba el backend. No representan categorías oficiales de alerta de NOAA.
