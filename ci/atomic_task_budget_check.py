"""A bounded advance cannot skip the current parser's blocking stylesheet.

The wall deadline used to end RunExternalTask in the middle of frame parsing.
The inline script ran with default styles and its initialization stayed wrong
after later advances. A pending external fetch outside a running task is still
bounded by wall_budget_check.py.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

from ruyijs import Context


class Handler(BaseHTTPRequestHandler):
    styles = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.path == '/frame':
            body = b'''<!doctype html><link rel="stylesheet" href="/slow.css">
<p class=loaded>child</p><script>
parent.innerRan=true;
parent.innerColor=getComputedStyle(document.querySelector('p')).color;
setTimeout(()=>parent.followup++,0);
</script>'''
            mime = 'text/html'
        else:
            Handler.styles += 1
            time.sleep(.35)
            body = b'.loaded { color: rgb(12, 34, 56); }'
            mime = 'text/css'
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run(base, mode):
    with Context(timeout=15) as ctx:
        ctx.configure_clock(mode, **({'epoch_ms': 1700000000000} if mode == 'logical' else {}))
        ctx.load_page(base, '<!doctype html><body>root</body>')
        ctx.eval('''window.innerRan=false;window.followup=0;window.afterAppend=false;
setTimeout(()=>{const f=document.createElement('iframe');f.src='/frame';
document.body.appendChild(f);window.afterAppend=true},0);void 0''')
        start = time.monotonic()
        state = ctx.advance(100, max_tasks=30, max_wall_ms=50)
        elapsed = time.monotonic() - start
        observed = ctx.eval('({innerRan,afterAppend,followup,color:window.innerColor})')
        assert observed == {'innerRan': True, 'afterAppend': True, 'followup': 0,
                            'color': 'rgb(12, 34, 56)'}, (state, observed)
        assert state['exhausted'] and .3 < elapsed < 5, (state, elapsed)
        ctx.advance(500, max_tasks=200, max_wall_ms=2000)
        assert ctx.eval("followup===1 && innerColor==='rgb(12, 34, 56)' && afterAppend"), ctx.eval('followup')
        print('ok', mode, 'blocking task finishes with its stylesheet; later task waits for next advance',
              round(elapsed, 3), flush=True)


def main():
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for mode in ['logical', 'system']:
            run(f'http://127.0.0.1:{server.server_port}/', mode)
        assert Handler.styles == 2, Handler.styles
    finally:
        server.shutdown()
        server.server_close()


if __name__ == '__main__':
    main()
