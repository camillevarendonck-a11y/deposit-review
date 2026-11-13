"""Local upload and analysis server. Start: python3 server.py"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import argparse
import json
from engine import analyze, DEFAULT_OBSERVATION, DEFAULT_TARGET

ROOT = Path(__file__).resolve().parent
MAX_BODY = 2 * 1024 * 1024
FILES = {'/': ('index.html', 'text/html; charset=utf-8'),
         '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
         '/review.js': ('review.js', 'text/javascript; charset=utf-8'),
         '/style.css': ('style.css', 'text/css; charset=utf-8'),
         '/template.csv': ('template.csv', 'text/csv; charset=utf-8'),
         '/sample.csv': ('deposits.csv', 'text/csv; charset=utf-8'),
         '/synthetic-demo.csv': ('synthetic_deposits.csv', 'text/csv; charset=utf-8'),
         '/realistic-example.csv': ('realistic-example.csv', 'text/csv; charset=utf-8')}

class Handler(BaseHTTPRequestHandler):
    def send(self, body, status=200, content_type='application/json'):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, allow_nan=False).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(body)

    def allowed(self):
        port = self.server.server_port
        hosts = (f'127.0.0.1:{port}', f'localhost:{port}')
        if self.headers.get('Host') not in hosts:
            return False
        return self.headers.get('Origin') in (None, *(f'http://{host}' for host in hosts))

    def do_GET(self):
        if not self.allowed():
            return self.send({'error': 'Local access only.'}, 403)
        path = urlsplit(self.path).path
        if path in ('/api/sample', '/api/demo'):
            large = path == '/api/demo'
            text = (ROOT / ('synthetic_deposits.csv' if large else 'deposits.csv')).read_text()
            try:
                result = analyze(text)
            except ValueError as error:
                return self.send({'error': 'Sample file: ' + str(error)}, 400)
            return self.send(dict(filename='Synthetic demo · 1,000 records' if large else 'Fictional sample · 5 records', csv_text=text,
                                  analysis=result, observation_time=DEFAULT_OBSERVATION, target_minutes=DEFAULT_TARGET))
        if path in FILES:
            name, mime = FILES[path]
            return self.send((ROOT / name).read_bytes(), content_type=mime)
        return self.send({'error': 'Not found'}, 404)

    def do_POST(self):
        if not self.allowed():
            return self.send({'error': 'Local access only.'}, 403)
        if urlsplit(self.path).path != '/api/analyze':
            return self.send({'error': 'Not found'}, 404)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= MAX_BODY:
                return self.send({'error': 'Use a CSV smaller than 2 MB.'}, 413)
            if self.headers.get('Content-Type', '').split(';')[0] != 'application/json':
                return self.send({'error': 'Send the analysis request as JSON.'}, 415)
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict):
                raise ValueError('Invalid request.')
            # Pure calculation: uploads are not saved and sample files are not replaced.
            result = analyze(data.get('csv_text'), data.get('observation_time'), data.get('target_minutes'))
            return self.send(result)
        except (ValueError, TypeError, UnicodeDecodeError) as error:
            return self.send({'error': str(error)}, 400)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8767)
    args = parser.parse_args()
    print(f'Deposit Review: http://127.0.0.1:{args.port}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
