"""Focus queries follow the active frame chain and retarget shadow descendants."""
from ruyijs import Context


FRAME = '''<!doctype html><style>html,body{margin:0}
input{position:absolute;left:5px;top:5px;width:70px;height:30px}</style>
<input id=inner>'''


def settle(ctx):
    for _ in range(6):
        ctx.advance(10, max_tasks=100)


with Context(timeout=20) as ctx:
    ctx.configure_clock('logical', epoch_ms=1700000000000)
    for url in ['https://focus.test/frame', 'https://other.focus.test/frame']:
        ctx.put_resource(url, FRAME)
    ctx.load_page('https://focus.test/', '''<!doctype html><input id=outer>
<iframe id=a src="/frame"></iframe><iframe id=b src="/frame"></iframe>
<iframe id=c src="https://other.focus.test/frame"
style="position:fixed;left:500px;top:200px;width:100px;height:70px;border:0"></iframe>
<div id=host></div><div id=frameHost></div>''')
    settle(ctx)
    read = '''(()=>({top:document.hasFocus(),a:a.contentDocument.hasFocus(),
b:b.contentDocument.hasFocus(),c:c.contentDocument.hasFocus(),
active:document.activeElement.id}))()'''
    assert ctx.eval(read) == {'top': True, 'a': False, 'b': False, 'c': False, 'active': ''}
    assert ctx.eval('document.implementation.createHTMLDocument().hasFocus()') is False
    ctx.eval("a.contentDocument.getElementById('inner').focus()")
    assert ctx.eval(read) == {'top': True, 'a': True, 'b': False, 'c': False, 'active': 'a'}
    ctx.eval("b.contentDocument.getElementById('inner').focus()")
    assert ctx.eval(read) == {'top': True, 'a': False, 'b': True, 'c': False, 'active': 'b'}
    # An inactive document retains its local active element. Focusing that same
    # node must nevertheless select the document's ancestor chain again.
    assert ctx.eval('a.contentDocument.activeElement.id') == 'inner'
    ctx.eval("a.contentDocument.getElementById('inner').focus()")
    assert ctx.eval(read)['active'] == 'a' and ctx.eval(read)['a'] is True
    ctx.eval('outer.focus()')
    assert ctx.eval(read) == {'top': True, 'a': False, 'b': False, 'c': False, 'active': 'outer'}
    # A native coordinate input activates a cross-origin child using the same
    # frame chain, without depending on page-replaceable iframe accessors.
    assert ctx.click_at(x=515, y=215, hold_ms=0)
    assert ctx.eval(read) == {'top': True, 'a': False, 'b': False, 'c': True, 'active': 'c'}
    ctx.eval('''window.nested=a.contentDocument.createElement('iframe');nested.src='/frame';
a.contentDocument.body.appendChild(nested);void 0''')
    settle(ctx)
    ctx.eval("nested.contentDocument.getElementById('inner').focus()")
    assert ctx.eval('document.activeElement===a&&a.contentDocument.activeElement===nested')
    assert ctx.eval('a.contentDocument.hasFocus()&&nested.contentDocument.hasFocus()&&!c.contentDocument.hasFocus()')
    ctx.eval('''window.root=host.attachShadow({mode:'closed'});
window.shadowInput=document.createElement('input');root.appendChild(shadowInput);
shadowInput.focus();void 0''')
    assert ctx.eval('document.activeElement===host&&root.activeElement===shadowInput')
    assert ctx.eval('!a.contentDocument.hasFocus()&&!nested.contentDocument.hasFocus()')
    ctx.eval('''window.frameRoot=frameHost.attachShadow({mode:'closed'});
window.shadowFrame=document.createElement('iframe');shadowFrame.src='/frame';
frameRoot.appendChild(shadowFrame);void 0''')
    settle(ctx)
    ctx.eval("shadowFrame.contentDocument.getElementById('inner').focus()")
    assert ctx.eval('document.activeElement===frameHost&&frameRoot.activeElement===shadowFrame')
    assert ctx.eval('shadowFrame.contentDocument.hasFocus()')
    # Retiring the embedding subtree invalidates focus membership immediately;
    # retained old document and element objects cannot reactivate that context.
    ctx.eval('''window.retired=shadowFrame.contentDocument;
frameHost.remove();retired.getElementById('inner').focus();void 0''')
    assert ctx.eval('!retired.hasFocus()&&document.activeElement===document.body')
    assert ctx.eval('6*7') == 42

assert ctx.closed and ctx._process.returncode == 0
print('ok document/frame focus membership, native cross-origin input, shadow retargeting and retirement', flush=True)
