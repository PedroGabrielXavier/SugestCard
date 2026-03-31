#!/usr/bin/env python3
"""Bodin Sugere - servidor local com proxy para Claude API"""
import json, os, mimetypes, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 3000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Lê variáveis do .env (se existir), depois api_key.txt, depois env do sistema
def _load_env(path):
    """Parser simples de .env — ignora comentários e linhas vazias."""
    if not os.path.isfile(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val

_load_env(os.path.join(BASE_DIR, '.env'))
_load_env(os.path.join(BASE_DIR, '.env.local'))

# Fallback: api_key.txt (legado)
_key_file = os.path.join(BASE_DIR, 'api_key.txt')
if os.path.isfile(_key_file) and not os.environ.get('ANTHROPIC_API_KEY'):
    with open(_key_file, encoding='utf-8') as _f:
        os.environ['ANTHROPIC_API_KEY'] = _f.read().strip()

ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
GOOGLE_CLIENT_ID  = os.environ.get('GOOGLE_CLIENT_ID', 'GOOGLE_CLIENT_ID_AQUI')

if not ANTHROPIC_API_KEY:
    raise SystemExit('ERRO: defina ANTHROPIC_API_KEY no arquivo .env ou em api_key.txt')

class Handler(BaseHTTPRequestHandler):

    # --- Arquivos estaticos ---
    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', ''):
            path = '/index.html'
        filepath = os.path.join(BASE_DIR, path.lstrip('/').replace('/', os.sep))
        if os.path.isfile(filepath):
            mime = mimetypes.guess_type(filepath)[0] or 'text/plain'
            with open(filepath, 'rb') as f:
                data = f.read()
            # Injeta GOOGLE_CLIENT_ID no HTML em tempo de execução
            if filepath.endswith('index.html'):
                data = data.replace(
                    b'GOOGLE_CLIENT_ID_AQUI',
                    GOOGLE_CLIENT_ID.encode('utf-8')
                )
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        else:
            self.send_response(404)
            self.end_headers()

    # --- Preflight CORS ---
    def do_OPTIONS(self):
        self.send_response(200)
        self._cors()
        self.end_headers()

    # --- Proxy para Claude API ---
    def do_POST(self):
        if self.path != '/api/claude':
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        req = urllib.request.Request(
            'https://api.anthropic.com/v1/messages',
            data=body,
            headers={
                'x-api-key': ANTHROPIC_API_KEY,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            method='POST',
        )

        try:
            with urllib.request.urlopen(req, timeout=40) as resp:
                resp_body = resp.read()
            self.send_response(200)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(resp_body)
        except urllib.error.HTTPError as e:
            err_body = e.read()
            self.send_response(e.code)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(err_body)
        except Exception as e:
            self.send_response(500)
            self._cors()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({'error': str(e)}).encode())

    def _cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def log_message(self, fmt, *args):
        print('  ' + fmt % args)

if __name__ == '__main__':
    # ThreadingHTTPServer permite multiplas conexoes (evita travar no refresh)
    server = ThreadingHTTPServer(('', PORT), Handler)
    server.allow_reuse_address = True
    print(f'Servidor rodando em http://localhost:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nEncerrando servidor...')
        server.server_close()
