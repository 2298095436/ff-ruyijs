"""Queued image work retains its element through GC and follows adoption."""
import base64

from ruyijs import Context


PIXEL = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jp1sAAAAASUVORK5CYII=")


def run(source, expected):
    with Context(timeout=20) as ctx:
        ctx.load_page('https://image-task.test/', '<!doctype html><body>control</body>')
        ctx.put_resource('https://image-task.test/pixel.png', PIXEL,
                         headers=[['content-type', 'image/png']])
        ctx.eval("window.imageEvents=[];" + source)
        # Collection/reclamation occurs before the queued source update. The
        # DOM task, rather than a page reference, must own the pending image.
        ctx.collect_garbage()
        ctx.eval("document.body.appendChild(document.createElement('p'));void 0")
        for _ in range(8):
            ctx.advance(10, max_tasks=100)
        actual = ctx.eval('imageEvents')
        assert actual == expected, (source, actual)
        assert ctx.eval('6*7') == 42
    assert ctx.closed and ctx._process.returncode == 0, ctx._process.returncode


if __name__ == '__main__':
    run("""(()=>{let e=document.createElement('div');
e.setAttribute('src','/unused');e=null})()""", [])
    print('ok non-image src never leaves a stale image task', flush=True)
    run("""(()=>{let e=new Image();
e.onload=()=>imageEvents.push('loaded');e.onerror=()=>imageEvents.push('error');
e.src='/pixel.png';e=null})()""", ['loaded'])
    print('ok detached image task retains its element until load', flush=True)
    run("""(()=>{const source=document.implementation.createHTMLDocument('other');
const e=source.createElement('div');e.setAttribute('src','/unused');
document.adoptNode(e);document.body.appendChild(e)})()""", [])
    print('ok non-image adoption does not enqueue obsolete image work', flush=True)
    run("""(()=>{const source=document.implementation.createHTMLDocument('other');
const e=source.createElement('img');e.onload=()=>imageEvents.push('adopted');
e.onerror=()=>imageEvents.push('error');e.src='/pixel.png';
document.adoptNode(e);document.body.appendChild(e)})()""", ['adopted'])
    print('ok queued image follows the original wrapper after adoption', flush=True)
    run("""(()=>{const e=new Image();
e.onload=()=>imageEvents.push('latest');e.onerror=()=>imageEvents.push('error');
e.src='/obsolete';e.src='/pixel.png'})()""", ['latest'])
    print('ok repeated source changes coalesce without dropping load', flush=True)
