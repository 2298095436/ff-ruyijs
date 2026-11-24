"""A full coordinate gesture preserves focus, cancellation and activation."""
import json

from ruyijs import Context


FRAME = '''<!doctype html><style>
html,body{margin:0}button{position:absolute;left:10px;top:12px;width:70px;
height:30px;border:0;padding:0}input{position:absolute;left:100px;top:12px;
width:20px;height:30px;margin:0}
</style><button id=real type=button>hold</button><input type=checkbox id=check>
<script>
const b=document.getElementById('real'),box=document.getElementById('check');
let held=false,task;
for(const type of ['pointerdown','mousedown','focus','pointerup','mouseup','click'])
b.addEventListener(type,e=>{
  const mode=document.body.getAttribute('data-mode')||'';
  if((mode==='pointer'&&type==='pointerdown')||(mode==='mouse'&&type==='mousedown'))e.preventDefault();
  if(type==='mousedown'){held=false;task=setTimeout(()=>held=true,200)}
  if(type==='mouseup')clearTimeout(task);
  parent.postMessage({type,focused:document.activeElement===b,held,trusted:e.isTrusted,
    view:e.view===window,x:e.clientX,y:e.clientY,sx:e.screenX,sy:e.screenY},'*');
});
box.addEventListener('click',e=>{if(document.body.getAttribute('data-mode')==='cancelClick')e.preventDefault()});
parent.postMessage({type:'ready'},'*');
</script>'''


def settle(ctx):
    for _ in range(6):
        ctx.advance(10, max_tasks=100)


def run(cross_origin):
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.put_resource('https://other.click.test/frame', FRAME,
                         headers=[['Content-Type', 'text/html']])
        ctx.load_page('https://click.test/', '''<!doctype html><style>
html,body{margin:0}#host{position:fixed;left:40px;top:50px;width:200px;height:120px}
#decoy{display:none}</style><div id=host><button id=decoy>hidden</button></div>
<script>window.messages=[];addEventListener('message',e=>messages.push(e.data));
decoy.onclick=()=>messages.push({type:'decoy'});</script>''')
        source = "f.src='https://other.click.test/frame';" if cross_origin else 'f.srcdoc=' + json.dumps(FRAME) + ';'
        ctx.eval('''(()=>{const s=document.getElementById('host').attachShadow({mode:'closed'}),
f=document.createElement('iframe');f.style.cssText='display:block;width:160px;height:80px;border:5px solid black';
''' + source + '''s.appendChild(f);window.fixtureFrame=f;return true})()''')
        settle(ctx)
        assert ctx.eval("messages.some(m=>m.type==='ready')"), ctx.eval('messages')
        ctx.eval('''window.fixtureWindow=fixtureFrame.contentWindow;
for(const key of ['contentWindow','contentDocument','getBoundingClientRect'])
Object.defineProperty(fixtureFrame,key,{get(){throw Error('page getter must not choose native input')}});
document.elementFromPoint=()=>{throw Error('page hit test must not run')};messages=[];void 0''')
        origin = ctx.eval('({x:mozInnerScreenX,y:mozInnerScreenY})')
        assert ctx.click_at(x=65, y=75, hold_ms=300)
        settle(ctx)
        rows = ctx.eval('messages')
        assert [r['type'] for r in rows] == ['pointerdown', 'mousedown', 'focus', 'pointerup', 'mouseup', 'click'], rows
        assert all(r['trusted'] and r['view'] for r in rows), rows
        last = rows[-1]
        assert last['focused'] and last['held'] and last['x'] == 20 and last['y'] == 20, last
        assert last['sx'] == origin['x'] + 65 and last['sy'] == origin['y'] + 75, last

        for mode, expected in [('pointer', ['pointerdown', 'pointerup', 'click']),
                               ('mouse', ['pointerdown', 'mousedown', 'pointerup', 'mouseup', 'click'])]:
            ctx.eval('fixtureWindow.document.body.setAttribute("data-mode",' + json.dumps(mode) +
                     ');fixtureWindow.document.getElementById("real").blur();void 0')
            ctx.eval('messages=[];void 0')
            assert ctx.click_at(x=65, y=75, hold_ms=300)
            settle(ctx)
            rows = ctx.eval('messages')
            assert [r['type'] for r in rows] == expected, rows
            assert not any(r['focused'] for r in rows), rows

        ctx.eval("fixtureWindow.document.body.setAttribute('data-mode','cancelClick');void 0")
        assert ctx.click_at(x=150, y=75, hold_ms=0)
        assert ctx.eval("fixtureWindow.document.getElementById('check').checked") is False
        ctx.eval("fixtureWindow.document.body.removeAttribute('data-mode');void 0")
        assert ctx.click_at(x=150, y=75, hold_ms=0)
        assert ctx.eval("fixtureWindow.document.getElementById('check').checked") is True
        assert ctx.click_at(x=-1, y=-1) is False
        try:
            ctx.click_at(x=65, y=75, hold_ms=60001)
        except Exception as error:
            assert '60000' in str(error), error
        else:
            raise AssertionError('Unbounded mouse hold was accepted')
        print('ok full native coordinate click, focus, hold, cancellation and activation in ' +
              ('cross-origin' if cross_origin else 'srcdoc') + ' closed-shadow frame', flush=True)


if __name__ == '__main__':
    run(False)
    run(True)
