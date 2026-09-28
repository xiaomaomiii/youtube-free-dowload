#!/usr/bin/env python3
"""
Backend local para YouTube Downloader Pro.
Usa yt-dlp (+ ffmpeg) para obtener metadatos y descargar el video/audio REAL,
y lo sirve desde el mismo origen (sin CORS ni instancias externas).

Uso:  python3 server.py   (luego abre http://localhost:8080)
"""
import http.server
import socketserver
import urllib.parse
import json
import subprocess
import os
import glob
import uuid
import tempfile
import re
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HTML_FILE = os.path.join(BASE_DIR, "youtube_downloader_pro.html")
TMP = tempfile.gettempdir()


def find_ffmpeg():
    """Localiza ffmpeg: binario del sistema o el que trae imageio-ffmpeg (pip)."""
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        if exe and os.path.exists(exe):
            return exe
    except Exception:
        pass
    return None


FFMPEG = find_ffmpeg()


def base_cmd():
    """Comando base de yt-dlp + ruta de ffmpeg si está disponible."""
    cmd = ["yt-dlp", "--no-playlist"]
    if FFMPEG:
        cmd += ["--ffmpeg-location", FFMPEG]
    # Cambiar de cliente ayuda a esquivar el "Sign in to confirm you're not a bot"
    cmd += ["--extractor-args", "youtube:player_client=android,web"]
    # Si se define un archivo de cookies, se usa (opcional, para videos con anti-bot)
    ck = os.environ.get("COOKIES_FILE", "").strip()
    if ck and os.path.exists(ck):
        cmd += ["--cookies", ck]
    return cmd


def sanitize(name):
    name = re.sub(r'[\\/:*?"<>|]', '_', name or "")
    name = name.strip().replace('\n', ' ')
    return (name[:150] or "video").strip()


def is_youtube(url):
    return bool(url) and ('youtube.com' in url or 'youtu.be' in url)


class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, *args):
        pass  # silenciar logs de acceso

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ('/', '/index.html'):
            self.serve_html()
        elif parsed.path == '/api/download':
            self.handle_download(parsed.query)
        else:
            self.send_error(404)

    def serve_html(self):
        try:
            with open(HTML_FILE, 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_error(404, 'No se encontro youtube_downloader_pro.html')

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == '/api/metadata':
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length) or b'{}')
            except Exception:
                return self._send_json({'error': 'Cuerpo inválido'}, 400)
            self.handle_metadata(body.get('url', ''))
        else:
            self.send_error(404)

    def handle_metadata(self, url):
        if not is_youtube(url):
            return self._send_json({'error': 'URL de YouTube inválida'}, 400)
        try:
            cmd = base_cmd() + ['--dump-json', '--no-warnings', url]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=90)
            if res.returncode != 0:
                err = (res.stderr or 'Error de yt-dlp').strip().splitlines()[-1][-300:]
                return self._send_json({'error': err}, 502)
            d = json.loads(res.stdout)
            self._send_json({
                'title': d.get('title') or 'Video',
                'uploader': d.get('uploader') or 'Canal',
                'thumbnail': d.get('thumbnail') or '',
                'duration': d.get('duration') or 0,
            })
        except subprocess.TimeoutExpired:
            self._send_json({'error': 'Tiempo agotado obteniendo metadatos'}, 504)
        except Exception as e:
            self._send_json({'error': str(e)[:300]}, 500)

    def handle_download(self, query):
        q = urllib.parse.parse_qs(query)
        url = (q.get('url') or [''])[0]
        fmt = (q.get('fmt') or ['mp4'])[0]
        quality = (q.get('q') or ['720'])[0]
        if not is_youtube(url):
            return self.send_error(400, 'URL inválida')

        token = uuid.uuid4().hex
        out_tmpl = os.path.join(TMP, f"yt_{token}_%(title)s.%(ext)s")
        try:
            if fmt == 'mp3':
                if not FFMPEG:
                    self.send_response(500)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(b'ffmpeg no disponible: no se puede convertir a MP3')
                    return
                cmd = base_cmd() + ['-x', '--audio-format', 'mp3',
                                    '--audio-quality', '320', '-o', out_tmpl, url]
            else:
                h = int(quality) if str(quality).isdigit() else 720
                # Si hay ffmpeg, se pueden unir video+audio de alta calidad.
                # Si no, se usa un formato ya combinado.
                if FFMPEG:
                    sel = f'bestvideo[height<={h}][ext=mp4]+bestaudio[ext=m4a]/best[height<={h}]'
                else:
                    sel = f'best[height<={h}][ext=mp4]/best[height<={h}]'
                cmd = base_cmd() + ['-f', sel, '--merge-output-format', 'mp4',
                                    '-o', out_tmpl, url]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
            if res.returncode != 0:
                msg = 'Error al descargar con yt-dlp: ' + (res.stderr or 'sin detalle').strip().splitlines()[-1][-500:]
                self.send_response(500)
                self.send_header('Content-Type', 'text/plain; charset=utf-8')
                self.end_headers()
                self.wfile.write(msg.encode('utf-8', 'ignore'))
                return
        except subprocess.TimeoutExpired:
            self.send_response(504)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'Tiempo de espera agotado durante la descarga')
            return

        files = glob.glob(os.path.join(TMP, f"yt_{token}_*"))
        if not files:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b'No se encontro el archivo generado')
            return

        fpath = max(files, key=os.path.getmtime)
        ext = 'mp3' if fmt == 'mp3' else 'mp4'
        # Quitar el prefijo temporal para que el nombre sea el título real
        base = re.sub(r'^yt_' + re.escape(token) + r'_', '', os.path.basename(fpath))
        fname = sanitize(os.path.splitext(base)[0]) + '.' + ext
        ctype = 'audio/mpeg' if fmt == 'mp3' else 'video/mp4'
        size = os.path.getsize(fpath)

        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(size))
        # filename* con UTF-8 para que los acentos y emojis no se rompan
        ascii_name = fname.encode('ascii', 'ignore').decode() or 'video.' + ext
        utf8_name = urllib.parse.quote(fname)
        self.send_header('Content-Disposition',
                         f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{utf8_name}')
        self.end_headers()
        try:
            with open(fpath, 'rb') as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        finally:
            try:
                os.remove(fpath)
            except Exception:
                pass


if __name__ == '__main__':
    PORT = int(os.environ.get('PORT', 8080))
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    with socketserver.ThreadingTCPServer(('0.0.0.0', PORT), Handler) as httpd:
        print(f"YouTube Downloader Pro -> http://localhost:{PORT}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServidor detenido.")
