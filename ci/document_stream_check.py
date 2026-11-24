"""Scripts written into live documents execute through the native loader.

Reproduces the blank verification iframe without any third-party challenge
code: a parent opens its blank iframe, writes an inline initializer and a
relative external script, then closes it. Also covers top-level and nested
writes, chunked input, repeated opens, and inert innerHTML script content.
"""
import json

from ruyijs import Context


BASE = 'https://document-stream.test/path/page#parent'
SCRIPT = 'https://document-stream.test/path/written.js'


def main():
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.put_resource(SCRIPT, 'window.externalRan=window.seed+2',
                         headers=[['Content-Type', 'application/javascript']])
        ctx.load_page(BASE, '<!doctype html><body><iframe id=f></iframe>')
        markup = ('<!doctype html><title>written</title><script>window.seed=40</script>'
                  '<script src="written.js"></script><body><p id=written>ready</p>')
        ctx.eval('(()=>{const d=document.querySelector("#f").contentDocument;d.open();d.write('
                 + json.dumps(markup) + ');d.close();return true})()')
        for _ in range(10):
            ctx.advance(20, max_tasks=50)
        state = ctx.eval('(()=>{const f=document.querySelector("#f"),d=f.contentDocument,w=f.contentWindow;return {title:d.title,ready:d.readyState,seed:w.seed??null,external:w.externalRan??null,url:d.URL,base:d.baseURI}})()')
        assert state['seed'] == 40 and state['external'] == 42, state
        assert state['ready'] == 'complete', state
        assert state['url'] == BASE.split('#')[0] and state['base'] == BASE.split('#')[0], state
        requests = [r for r in ctx.net_log() if r['url'] == SCRIPT]
        assert requests and all(r['status'] == 200 and r['matched'] for r in requests), requests
        print('ok written iframe inline and relative external scripts execute with the creator URL', flush=True)

        ctx.eval("document.querySelector('#f').contentDocument.body.innerHTML='<script>window.inertRan=true<\\/script>';void 0")
        ctx.advance(10, max_tasks=20)
        assert ctx.eval("document.querySelector('#f').contentWindow.inertRan===undefined")
        print('ok innerHTML scripts remain inert', flush=True)

    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page(BASE, '<!doctype html><title>old</title>')
        markup = '<!doctype html><body><script>window.order=[1];document.write("<b id=nested>nested</b>");order.push(2)</script><script>order.push(3)</script>'
        ctx.eval('document.open();document.write(' + json.dumps(markup) + ');document.close();void 0')
        ctx.advance(10, max_tasks=20)
        state = ctx.eval('({order:window.order??null,nested:document.querySelector("#nested")?.textContent,ready:document.readyState})')
        assert state == {'order': [1, 2, 3], 'nested': 'nested', 'ready': 'complete'}, state
        print('ok top-level writes run scripts and nested markup in order', flush=True)
        ctx.eval('document.open();document.write("<!doctype html><script>window.chunkRan=");document.write("42<\\/script>");document.close();void 0')
        ctx.advance(10, max_tasks=20)
        assert ctx.eval('window.chunkRan') == 42
        print('ok repeated open and a script split across write calls', flush=True)


if __name__ == '__main__':
    main()
