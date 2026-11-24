"""Already due page work progresses while HTTP completions remain ready.

The old driver always ran an external completion first, including when every
advance had a one-task budget. Six local replies reproduce that starvation
without relying on a public endpoint or a page-specific timer.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import time

from ruyijs import Context


class Handler(BaseHTTPRequestHandler):
    served = 0
    condition = threading.Condition()

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b"complete"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        with Handler.condition:
            Handler.served += 1
            Handler.condition.notify_all()


def ready_batch(ctx, count=6):
    with Handler.condition:
        expected = Handler.served + count
    ctx.eval("globalThis.replies=[];for(let i=0;i<" + str(count) +
             ";i++)fetch('/reply'+i).then(r=>r.text()).then(t=>replies.push(t))")
    with Handler.condition:
        assert Handler.condition.wait_for(lambda: Handler.served >= expected, timeout=12), Handler.served
    # Responses have been written; let the native helper finish posting them
    # without running any page tasks before the bounded advance below.
    time.sleep(.25)


def check(base, clock):
    with Context(timeout=20) as ctx:
        ctx.configure_clock(clock, **({"epoch_ms": 1700000000000} if clock == "logical" else {}))
        ctx.load_page(base, "<!doctype html><title>task sources</title>")
        ready_batch(ctx)
        ctx.eval("globalThis.timer=0;setTimeout(()=>timer++,0)")
        for _ in range(2):
            result = ctx.advance(0, max_tasks=1, max_wall_ms=1000)
            assert result["executed"] == 1, result
        state = ctx.eval("({timer,replies:replies.length})")
        assert state["timer"] == 1 and state["replies"] >= 1, state
        print("ok", clock, "due timer and HTTP both progress across one-task calls", state, flush=True)
        ctx.advance(100, max_tasks=1000, max_wall_ms=2000)
        assert ctx.eval("replies.length===6 && replies.every(r=>r==='complete')"), ctx.eval("replies")

        # Several due callbacks must also make progress in one bounded call,
        # while leaving enough slots for the ready external source.
        ready_batch(ctx)
        ctx.eval("globalThis.order=[];for(let i=0;i<3;i++)setTimeout(()=>order.push(i),0)")
        result = ctx.advance(0, max_tasks=6, max_wall_ms=1000)
        state = ctx.eval("({order,replies:replies.length})")
        assert state["order"] == [0, 1, 2] and state["replies"] >= 2, (result, state)
        ctx.advance(100, max_tasks=1000, max_wall_ms=2000)
        assert ctx.eval("replies.length===6")
        print("ok", clock, "both task sources progress within a bounded call", state, flush=True)

        if clock == "logical":
            ready_batch(ctx)
            ctx.eval("globalThis.future=false;setTimeout(()=>future=true,50)")
            ctx.advance(0, max_tasks=20, max_wall_ms=1000)
            assert ctx.eval("!future && replies.length===6")
            ctx.advance(50, max_tasks=20, max_wall_ms=1000)
            assert ctx.eval("future")
            print("ok logical future timers retain their deadlines", flush=True)


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        for clock in ("logical", "system"):
            check(f"http://127.0.0.1:{server.server_port}/", clock)
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
