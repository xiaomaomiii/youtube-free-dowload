# YouTube Downloader Pro

Descargador de video/audio de YouTube. Muestra los **metadatos reales**
(título, canal, miniatura) y descarga el **archivo real** en MP4 o MP3.

Hay **dos versiones**, elige según dónde lo vayas a alojar:

| Versión | Archivo | Dónde funciona | Cómo descarga |
|---|---|---|---|
| **Estática** | `index.html` | GitHub Pages, Netlify, Vercel, cualquier hosting de archivos | API pública Cobalt (con instancias de respaldo) |
| **Con backend** | `server.py` + `youtube_downloader_pro.html` | Tu PC, VPS, Render, Railway | yt-dlp + ffmpeg en tu propio servidor |

> **Importante:** GitHub Pages **no ejecuta Python**. Si subes solo `server.py`
> a Pages, verás únicamente este README y no la aplicación. Para Pages usa
> `index.html`.

## Publicar en GitHub Pages (lo más rápido)

1. Sube `index.html` a la **raíz** del repositorio.
2. En GitHub: *Settings → Pages → Build and deployment → Source: Deploy from a branch → Branch: main, Folder: / (root)*.
3. Espera 1-2 minutos y abre `https://<tu-usuario>.github.io/<tu-repo>/`.

No hay que instalar nada: la página es un único archivo HTML.

## Estructura

| Archivo | Qué hace |
|---|---|
| `index.html` | **Versión estática** lista para GitHub Pages (metadatos por oEmbed, descarga por Cobalt) |
| `server.py` | Servidor HTTP: sirve la web y expone `/api/metadata` y `/api/download` |
| `youtube_downloader_pro.html` | Interfaz (Tailwind) que consume esas dos rutas |
| `requirements.txt` | Dependencias Python: `yt-dlp`, `imageio-ffmpeg` |
| `Procfile` | Para desplegar en Railway / Heroku / Render |

### Backend propio opcional en la versión estática

`index.html` tiene un icono de **ajustes** (arriba a la derecha). Si despliegas
`server.py` en Render/Railway, pega ahí su URL (por ejemplo
`https://mi-servidor.onrender.com`) y la página pasará a usar **yt-dlp** en lugar
del servicio público. Se guarda en `localStorage`.

## Requisitos

- Python 3.8 o superior
- `ffmpeg` en el sistema **o** instalar `imageio-ffmpeg` (incluido en `requirements.txt`,
  trae su propio binario, así que no hace falta instalar ffmpeg aparte)

## Instalación y uso en local

```bash
pip install -r requirements.txt
python3 server.py
```

Abre **http://localhost:8080**

Para usar otro puerto:

```bash
PORT=3000 python3 server.py
```

Para desplegar en un servidor y que escuche en todas las interfaces ya está así por
defecto (`0.0.0.0`).

## Cómo funciona

1. Pegas la URL y pulsas **Analizar** → el front llama a `POST /api/metadata`,
   el backend ejecuta `yt-dlp --dump-json` y devuelve título, canal, miniatura y duración reales.
2. Eliges formato (MP4/MP3) y calidad → el front navega a `GET /api/download?url=...&fmt=...&q=...`.
3. El backend descarga con yt-dlp a un temporal y lo devuelve con
   `Content-Disposition: attachment`, así el navegador guarda el archivo **completo**.

## API

### `POST /api/metadata`

```json
{ "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ" }
```

Respuesta:

```json
{ "title": "...", "uploader": "...", "thumbnail": "...", "duration": 213 }
```

### `GET /api/download?url=...&fmt=mp4|mp3&q=1080|720|480|360`

Devuelve el binario del video/audio con `Content-Disposition: attachment`.

## Despliegue en la web (gratis)

El proyecto lee la variable de entorno `PORT`, así que funciona en cualquier PaaS:

- **Railway / Heroku**: sube el repo, usa el `Procfile` incluido.
- **Render**: *Build Command* `pip install -r requirements.txt`,
  *Start Command* `python3 server.py`.
- **PythonAnywhere / VPS**: `pip install -r requirements.txt && python3 server.py`.

> Nota: en hosts gratuitos tipo PythonAnywhere el acceso a YouTube puede estar
> limitado. Railway, Render o un VPS pequeño funcionan mejor.

## Solución de problemas

- **"ffmpeg no disponible" al pedir MP3**: instala ffmpeg en el sistema
  (`sudo apt install ffmpeg`) o reinstala `pip install imageio-ffmpeg`.
- **Error 500 con "Sign in to confirm you're not a bot"**: YouTube pide cookies en
  algunos videos. Exporta tus cookies de YouTube a `cookies.txt` (con la extensión
  *Get cookies.txt LOCALLY*) y arranca con `COOKIES_FILE=/ruta/cookies.txt python3 server.py`.
  Actualizar yt-dlp también ayuda mucho: `pip install -U yt-dlp`.
- **El archivo sale con otro nombre o cortado**: asegúrate de abrir la web desde la
  URL del servidor (no el archivo HTML suelto con doble clic), y de descargar en una
  pestaña normal, no dentro de un visor embebido.

## Aviso

Descarga solo contenido del que tengas derechos o con permiso del autor.
El uso de esta herramienta es responsabilidad de quien la ejecuta.
