"""Native pointer input follows painted targets, closed shadows and frames.

All documents are local fixtures. A hidden light-DOM button must never receive
the event intended for a closed shadow's iframe. Script-overridden DOM getters
must not redirect native input or leak a closed shadow to public queries.
"""
import json

from ruyijs import Context


FRAME = '''<!doctype html><style>
html,body{margin:0;padding:0}button{position:absolute;left:10px;top:12px;
width:70px;height:30px;border:0;padding:0}
</style><button id=real>hold</button><script>
const b=document.querySelector('#real');
b.addEventListener('pointerdown',e=>parent.postMessage({kind:'down',
  trusted:e.isTrusted,target:e.target===b,view:e.view===window,
  x:e.clientX,y:e.clientY,sx:e.screenX,sy:e.screenY,buttons:e.buttons},'*'));
parent.postMessage({kind:'ready'},'*');
</script>'''


def settle(ctx):
    for _ in range(6):
        ctx.advance(10, max_tasks=50)


def frame_check(cross_origin):
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.put_resource('https://other.pointer.test/frame', FRAME,
                         headers=[['Content-Type', 'text/html']])
        ctx.load_page('https://pointer.test/', '''<!doctype html><style>
html,body{margin:0;padding:0}#host{position:fixed;left:40px;top:50px;
width:200px;height:120px}#decoy{display:none}
</style><div id=host><button id=decoy>hidden</button></div>
<script>window.messages=[];addEventListener('message',e=>messages.push(e.data));
document.querySelector('#decoy').addEventListener('pointerdown',()=>messages.push({kind:'decoy'}));
</script>''')
        src = "f.src='https://other.pointer.test/frame';" if cross_origin else 'f.srcdoc=' + json.dumps(FRAME) + ';'
        ctx.eval('''(()=>{const h=document.querySelector('#host'),s=h.attachShadow({mode:'closed'}),
f=document.createElement('iframe');f.style.cssText='display:block;width:160px;height:80px;border:5px solid black;';
''' + src + '''s.appendChild(f);window.frameForTest=f;return true})()''')
        settle(ctx)
        assert ctx.eval("messages.some(m=>m.kind==='ready')"), ctx.eval('messages')
        assert ctx.eval("document.querySelector('#host').shadowRoot===null && document.querySelectorAll('iframe').length===0")
        ctx.eval('''(()=>{const f=window.frameForTest;
for(const k of ['contentWindow','contentDocument','getBoundingClientRect'])
Object.defineProperty(f,k,{get(){throw Error('page getter must not run')}});
Object.defineProperty(document,'elementFromPoint',{value(){throw Error('page hit test must not run')}});
return true})()''')
        screen = ctx.eval('({x:mozInnerScreenX,y:mozInnerScreenY})')
        before = ctx.eval('messages')
        hit = ctx.inspect_pointer(x=65, y=75)
        assert hit['tag'] == 'button' and hit['id'] == 'real' and hit['frameDepth'] == 1, hit
        assert hit['clientX'] == 20 and hit['clientY'] == 20, hit
        assert hit['rect']['x'] == 10 and hit['rect']['y'] == 12, hit
        assert hit['text'] == 'hold' and hit['ancestors'][0]['text'] == 'hold', hit
        assert ctx.eval('messages') == before
        assert ctx.inspect_pointer(x=-1, y=-1) is None
        assert ctx.dispatch_pointer('pointerdown', x=65, y=75,
                                    bubbles=True, composed=True, cancelable=True,
                                    pointerId=1, pointerType='mouse', isPrimary=True,
                                    button=0, buttons=1)
        settle(ctx)
        messages = ctx.eval('messages')
        downs = [m for m in messages if m.get('kind') == 'down']
        assert len(downs) == 1 and not any(m.get('kind') == 'decoy' for m in messages), messages
        event = downs[0]
        assert event['trusted'] and event['target'] and event['view'] and event['buttons'] == 1, event
        assert event['x'] == 20 and event['y'] == 20, event
        assert event['sx'] == screen['x'] + 65 and event['sy'] == screen['y'] + 75, event
        assert ctx.dispatch_pointer('pointerdown', x=-1, y=-1) is False
        print('ok native pointer enters closed shadow and ' +
              ('cross-origin' if cross_origin else 'srcdoc') + ' iframe with local and screen coordinates', flush=True)


def paint_check():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://pointer.test/', '''<!doctype html><style>
html,body{margin:0}#under,#over{position:fixed;left:10px;top:10px;width:80px;height:40px}
#over{z-index:2}#under{z-index:1}
</style><button id=under>under</button><button id=over>over</button>
<script>window.hits=[];for(const e of document.querySelectorAll('button'))
e.addEventListener('pointerdown',()=>hits.push(e.id));</script>''')
        assert ctx.dispatch_pointer('pointerdown', x=30, y=25, bubbles=True)
        assert ctx.eval('hits') == ['over']
        ctx.eval("document.querySelector('#over').style.pointerEvents='none'")
        assert ctx.dispatch_pointer('pointerdown', x=30, y=25, bubbles=True)
        assert ctx.eval('hits') == ['over', 'under']
        ctx.dispatch_input('pointerdown', target="document.querySelector('#under')", bubbles=True)
        assert ctx.eval('hits') == ['over', 'under', 'under']
        for bad in (float('nan'), float('inf'), True, '10'):
            try:
                ctx.dispatch_pointer('pointerdown', x=bad, y=0)
            except (TypeError, ValueError):
                pass
            else:
                raise AssertionError('Invalid coordinates accepted')
        print('ok native pointer respects paint order and pointer-events; expression input still works', flush=True)


if __name__ == '__main__':
    frame_check(False)
    frame_check(True)
    paint_check()
