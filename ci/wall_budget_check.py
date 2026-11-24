"""A bounded advance must yield pending HTTP and preserve its Context.

The local response is released by Python only after advance returns; an
unbounded logical wait cannot accidentally pass by waiting for a short sleep.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

from ruyijs import Context


def main():
    release = threading.Event()
    requested = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            requested.set()
            release.wait(8)
            data = b'released'
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = 'http://127.0.0.1:' + str(server.server_port) + '/'
    try:
        with Context(timeout=3, http_timeout=10, http_read_timeout=10) as ctx:
            ctx.configure_clock('logical', epoch_ms=1700000000000)
            ctx.load_page(base, '<!doctype html><title>wall budget</title>')
            ctx.eval("window.done=false;fetch('/held').then(r=>r.text()).then(t=>{window.done=t==='released'});void 0")
            start = time.monotonic()
            state = ctx.advance(0, max_tasks=1, max_wall_ms=40)
            elapsed = time.monotonic() - start
            assert elapsed < 1, (elapsed, state)
            assert state['exhausted'] and not ctx.closed and not ctx.eval('done'), state
            assert state['now_ms'] == 0, state
            print('ok bounded logical advance yielded pending HTTP in', round(elapsed, 3), 'seconds', flush=True)
            release.set()
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline and not ctx.eval('done'):
                ctx.advance(20, max_tasks=20, max_wall_ms=50)
            assert ctx.eval('done') and requested.is_set(), ctx.net_log()
            assert ctx.eval('6*7') == 42
            print('ok the same Context completed its original fetch after release', flush=True)
            ctx.eval('window.calls=0;setTimeout(()=>calls++,0);void 0')
            state = ctx.advance(10, max_wall_ms=0)
            assert state['exhausted'] and ctx.eval('calls') == 0, state
            ctx.advance(10)
            assert ctx.eval('calls') == 1
            print('ok zero wall budget retains timers for a later call', flush=True)
        with Context(timeout=3) as ctx:
            ctx.configure_clock('system')
            ctx.eval('void 0')
            start = time.monotonic()
            state = ctx.advance(2000, max_wall_ms=30)
            assert time.monotonic() - start < 1, state
            assert state['exhausted'], state
            assert not ctx.closed and ctx.eval('6*7') == 42
            print('ok wall budget bounds system-clock waiting', flush=True)
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == '__main__':
    main()
