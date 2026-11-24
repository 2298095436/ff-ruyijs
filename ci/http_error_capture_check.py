"""Error diagnostics preserve the real response and do not repeat HTTP calls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import tempfile
import threading

from ruyijs import Context


BODY = b'<!doctype html><title>original denial</title><p>real response</p>'


class Handler(BaseHTTPRequestHandler):
    count = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        Handler.count += 1
        self.send_response(200 if self.path == '/ok' else 403)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Set-Cookie', 'test_secret=do-not-capture')
        self.send_header('Content-Length', str(len(BODY)))
        self.end_headers()
        self.wfile.write(BODY)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    names = ['RUYIJS_HTTP_ERROR_DIR', 'RUYIJS_HTTP_CAPTURE_DIR', 'RUYIJS_HTTP_CAPTURE_URL']
    previous = {name: os.environ.pop(name, None) for name in names}
    try:
        with tempfile.TemporaryDirectory(prefix='ruyijs-errors-') as temporary:
            folder = Path(temporary)
            base = f'http://127.0.0.1:{server.server_port}'
            with Context(timeout=15) as ctx:
                ctx.navigate(base + '/disabled')
                assert ctx.eval('document.title') == 'original denial'
            assert list(folder.iterdir()) == []
            assert Handler.count == 1
            os.environ['RUYIJS_HTTP_ERROR_DIR'] = str(folder)
            with Context(timeout=15) as ctx:
                ctx.navigate(base + '/blocked')
                assert ctx.eval('document.title') == 'original denial'
                assert ctx.net_log()[-1]['status'] == 403
                ctx.navigate(base + '/ok')
            records = list(folder.glob('*.json'))
            assert len(records) == 1, records
            metadata = json.loads(records[0].read_text())
            assert metadata['status'] == 403 and metadata['url'] == base + '/blocked', metadata
            assert records[0].with_suffix('.body').read_bytes() == BODY
            assert all(name.lower() != 'set-cookie' for name, _ in metadata['headers'])
            assert metadata['capturedBytes'] == len(BODY) == metadata['bodyBytes']
            assert Handler.count == 3, Handler.count
            print('ok error capture is opt-in, records the original bytes and omits cookie headers', flush=True)
            print('ok successful responses are not captured and no diagnostic request is sent', flush=True)
            os.environ['RUYIJS_HTTP_CAPTURE_DIR'] = str(folder)
            # A directory alone must not silently enable broad collection.
            with Context(timeout=15) as ctx:
                ctx.navigate(base + '/ok')
            assert len(list(folder.glob('*.json'))) == 1
            os.environ['RUYIJS_HTTP_CAPTURE_URL'] = '/ok'
            with Context(timeout=15) as ctx:
                ctx.navigate(base + '/ok')
                assert ctx.eval('document.title') == 'original denial'
                assert ctx.net_log()[-1]['status'] == 200
            records = [json.loads(path.read_text()) for path in folder.glob('*.json')]
            selected = [record for record in records if record['status'] == 200]
            assert len(records) == 2 and len(selected) == 1, records
            assert selected[0]['url'] == base + '/ok'
            assert all(name.lower() != 'set-cookie' for name, _ in selected[0]['headers'])
            assert Handler.count == 5, Handler.count
            print('ok successful response capture requires a URL filter and sends no extra requests', flush=True)
    finally:
        for name, value in previous.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
