#!/usr/bin/env python3
"""BodinhaSugere - servidor local com proxy para Claude API"""
import json, os, mimetypes, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 3000
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Lê a chave do arquivo api_key.txt (não commitado no git)
_key_file = os.path.join(BASE_DIR, 'api_key.txt')
if os.path.isfile(_key_file):
    with open(_key_file, encoding='utf-8') as _f:
        ANTHROPIC_API_KEY = _f.read().strip()
else:
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')

if not ANTHROPIC_API_KEY:
    raise SystemExit('ERRO: crie o arquivo api_key.txt com sua chave Anthropic, ou defina a variavel de ambiente ANTHROPIC_API_KEY')

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
    server = HTTPServer(('', PORT), Handler)
    print(f'Servidor rodando em http://localhost:{PORT}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('Encerrado.')
