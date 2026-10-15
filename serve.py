"""
serve.py
~~~~~~~~
Serves dashboard.html plus a tiny JSON API over the data/ folder so the
dashboard can list and auto-refresh runs while main.py is working.

    python serve.py          # then open http://localhost:8787

No dependencies beyond the standard library.
"""
import json
import os
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8787


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, *_):      # keep the console quiet
        pass

    def _json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/':
            self.path = '/dashboard.html'
        if self.path.startswith('/api/runs'):
            files = []
            if os.path.isdir(DATA):
                for name in os.listdir(DATA):
                    p = os.path.join(DATA, name)
                    if os.path.isfile(p) and name.endswith(('.csv', '.log')):
                        files.append({'name': name, 'size': os.path.getsize(p),
                                      'mtime': os.path.getmtime(p)})
            files.sort(key=lambda f: f['mtime'], reverse=True)
            return self._json(files)
        if self.path.startswith('/data/'):
            self.send_header_nocache = True
        return super().do_GET()

    def end_headers(self):
        if self.path.startswith('/data/'):
            self.send_header('Cache-Control', 'no-store')
        super().end_headers()


if __name__ == '__main__':
    os.makedirs(DATA, exist_ok=True)
    print(f'WQ-Brain dashboard  ->  http://localhost:{PORT}')
    print('Ctrl+C to stop.')
    try:
        ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
    except KeyboardInterrupt:
        pass
