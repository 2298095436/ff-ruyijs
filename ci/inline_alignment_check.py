"""Inline alignment must agree with geometry and native pointer hit testing.

These are local CSS fixtures, with no site scripts or recorded responses.
CSS 2.2 section 16.2 aligns inline-level boxes inside the line's content box.
"""
import json

from ruyijs import Context


def near(actual, expected):
    assert abs(actual - expected) < .02, (actual, expected)


def geometry_check():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://alignment.test/', '''<!doctype html><style>
html,body{margin:0}#line{width:528px;text-align:center}
#button{display:inline-block;width:203px;height:48px;position:relative}
#inside{width:40px;height:20px}#block{width:80px;height:10px}
</style><div id=line><div id=button role=button><div id=inside></div></div></div>
<div id=block></div>''')
        read = '''(()=>Object.fromEntries(['line','button','inside','block'].map(
id=>[id,document.getElementById(id).getBoundingClientRect().toJSON()])))()'''
        boxes = ctx.eval(read)
        near(boxes['button']['x'], 162.5)
        near(boxes['inside']['x'], 162.5)
        near(boxes['block']['x'], 0)
        assert any(a['role'] == 'button' for a in ctx.inspect_pointer(x=264, y=24)['ancestors'])
        # Each mutation reuses a warm layout; repeated changes must not retain
        # a stale line offset or accumulate translations in child subtrees.
        for width, align, expected in [(600, 'right', 397), (400, 'center', 98.5),
                                       (300, 'left', 0), (528, 'center', 162.5)]:
            ctx.eval(f"line.style.width='{width}px';line.style.textAlign='{align}';void 0")
            boxes = ctx.eval(read)
            near(boxes['button']['x'], expected)
            near(boxes['inside']['x'], expected)
        print('ok centered/right inline blocks, descendants, native hits and warm mutations', flush=True)


def line_check():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://alignment.test/', '''<!doctype html><style>
html,body{margin:0}.line{width:300px;text-align:center}
.item{display:inline-block;height:20px}#a{width:60px}#b{width:80px}
#break{height:10px;width:30px}#c{width:40px}
</style><div class=line id=line><span class=item id=a></span><span class=item id=b></span><div id=break></div><span class=item id=c></span></div>''')
        read = "(()=>Object.fromEntries(['a','b','break','c'].map(id=>[id,document.getElementById(id).getBoundingClientRect().x])))()"
        assert ctx.eval(read) == {'a': 80, 'b': 140, 'break': 0, 'c': 130}
        ctx.eval("line.style.textAlign='right';void 0")
        assert ctx.eval(read) == {'a': 160, 'b': 220, 'break': 0, 'c': 260}
        ctx.eval("line.innerHTML='<span id=only class=item style=\"width:60px\"></span>';line.style.direction='rtl';line.style.textAlign='start';void 0")
        near(ctx.eval("only.getBoundingClientRect().x"), 240)
        ctx.eval("line.style.textAlign='end';void 0")
        near(ctx.eval("only.getBoundingClientRect().x"), 0)
        ctx.eval("line.style.cssText='width:100px;text-align:center';only.style.width='140px';void 0")
        near(ctx.eval("only.getBoundingClientRect().x"), -20)
        print('ok each inline line aligns separately; blocks, logical alignment and overflow', flush=True)


def auto_width_check():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://alignment.test/', '''<!doctype html><style>
html,body{margin:0}.line{width:400px;text-align:center}
#auto,#inner{display:inline-block}#inner{width:80px;height:20px}
</style><div class=line><span id=auto><span id=inner></span></span></div>
<div class=line><span id=outer><span id=nested>text</span></span></div>''')
        near(ctx.eval('auto.getBoundingClientRect().width'), 80)
        near(ctx.eval('auto.getBoundingClientRect().x'), 160)
        near(ctx.eval('inner.getBoundingClientRect().x'), 160)
        boxes = ctx.eval('({outer:outer.getBoundingClientRect().toJSON(),nested:nested.getBoundingClientRect().toJSON()})')
        near(boxes['outer']['x'], (400 - boxes['outer']['width']) / 2)
        near(boxes['nested']['x'], boxes['outer']['x'])
        print('ok shrink-to-fit uses final width and ordinary inline boxes do not align again', flush=True)


def positioned_check():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://alignment.test/', '''<!doctype html><style>
html,body{margin:0}#line{width:300px;text-align:center}
#item{display:inline-block;width:100px;height:30px}
#fixed{position:fixed;left:7px;top:5px;width:10px;height:10px}
#absolute{position:absolute;left:11px;top:6px;width:10px;height:10px}
</style><div id=line><div id=item><div id=fixed></div><div id=absolute></div></div></div>''')
        near(ctx.eval('item.getBoundingClientRect().x'), 100)
        near(ctx.eval('fixed.getBoundingClientRect().x'), 7)
        near(ctx.eval('absolute.getBoundingClientRect().x'), 11)
        ctx.eval("item.style.position='relative';void 0")
        near(ctx.eval('item.getBoundingClientRect().x'), 100)
        near(ctx.eval('absolute.getBoundingClientRect().x'), 111)
        near(ctx.eval('fixed.getBoundingClientRect().x'), 7)
        print('ok alignment preserves viewport and external absolute containing blocks', flush=True)


def frame_check():
    frame = '''<!doctype html><style>html,body{margin:0}
#line{width:100%;text-align:center}#button{display:inline-block;width:203px;height:48px}
</style><div id=line><div id=button role=button>hold</div></div><script>
button.addEventListener('mousedown',e=>parent.postMessage({trusted:e.isTrusted,
target:e.target.id,x:e.clientX,y:e.clientY},'*'));</script>'''
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://alignment.test/', '''<!doctype html><style>
html,body{margin:0}#host{position:fixed;left:40px;top:50px;width:530px;height:50px}
</style><div id=host></div><script>window.messages=[];addEventListener('message',e=>messages.push(e.data))</script>''')
        ctx.eval("(()=>{const s=host.attachShadow({mode:'closed'}),f=document.createElement('iframe');"
                 "f.style.cssText='width:530px;height:50px;border:0;display:block';f.srcdoc=" +
                 json.dumps(frame) + ";s.append(f);return true})()")
        for _ in range(6):
            ctx.advance(10, max_tasks=50)
        hit = ctx.inspect_pointer(x=305, y=74)
        assert hit['frameDepth'] == 1 and hit['id'] == 'button', hit
        near(hit['rect']['x'], 163.5)
        assert ctx.dispatch_pointer('mousedown', x=305, y=74, bubbles=True, button=0, buttons=1)
        for _ in range(3):
            ctx.advance(10, max_tasks=50)
        assert ctx.eval('messages') == [{'trusted': True, 'target': 'button', 'x': 265, 'y': 24}]
        print('ok closed-shadow iframe center hits the aligned button with local coordinates', flush=True)


if __name__ == '__main__':
    geometry_check()
    line_check()
    auto_width_check()
    positioned_check()
    frame_check()
