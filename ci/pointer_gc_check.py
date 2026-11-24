"""Coordinate input and RPC allocation must not corrupt cross-zone shape caches.

The RPC dictionary is created in the host codec zone and amended while input
runs in the page's zone. Previously those amendments bypassed realm wrapping;
later codec allocation exposed a dangling shape-cache pointer at destruction.
"""
from ruyijs import Context


def check(send_input):
    ctx = Context(timeout=20)
    process = ctx._process
    try:
        ctx.load_page('https://pointer-gc.test/', '''<!doctype html>
<button style="width:200px;height:50px">hold</button>''')
        if send_input:
            for kind in ('pointerover', 'pointerenter', 'mouseover', 'mouseenter',
                         'pointermove', 'mousemove', 'pointerdown', 'mousedown',
                         'pointerup', 'mouseup'):
                assert ctx.dispatch_pointer(kind, x=20, y=20, bubbles=True,
                    cancelable=True, composed=True, button=0, buttons=1, detail=1,
                    pointerId=0, pointerType='mouse', isPrimary=True,
                    width=1, height=1, pressure=.5)
        # The same bounded typed snapshots as a real diagnostic session. Allow
        # ordinary allocation-triggered GC rather than forcing all zones to be
        # collected together, which would conceal the lifetime defect.
        for _ in range(100):
            rows = ctx.eval('Array.from({length:1500},(_,i)=>({a:i,b:String(i),c:[1,2,3]}))')
            assert len(rows) == 1500 and rows[-1]['a'] == 1499
    finally:
        ctx.close()
    assert process is not None and process.returncode == 0, (
        'native runtime failed during shutdown', send_input, process.returncode)
    print('ok coordinate input / codec GC / native shutdown: ' + str(send_input), flush=True)


if __name__ == '__main__':
    check(False)
    check(True)
    check(True)
