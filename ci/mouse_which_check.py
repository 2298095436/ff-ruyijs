"""Mouse-family which follows pinned Firefox160 MouseEvent::Which()."""
from ruyijs import Context


def main():
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://mouse.test/', '''<!doctype html><style>
html,body{margin:0}button{width:180px;height:50px}</style><button id=hold>Hold</button>
<script>window.reads=[];window.state='idle';let timer;
for(const type of ['pointerdown','mousedown','pointerup','mouseup','click'])
hold.addEventListener(type,e=>{reads.push([e.type,e.button,e.which,e.isTrusted]);
if(e.type==='mousedown'&&e.which===1){state='holding';timer=setTimeout(()=>state='held',500)}
if(e.type==='mouseup'&&e.which===1){clearTimeout(timer);if(state==='holding')state='released'}});
</script>''')
        assert ctx.eval("""(()=>{for(const C of [MouseEvent,PointerEvent,WheelEvent,DragEvent])
for(const button of [-1,0,1,2,3,4]){const e=new C('test',{button,which:77});
if(e.which!==button+1)return false;
Object.defineProperty(e,'button',{get(){throw Error('must use original button')}});
if(e.which!==button+1)return false}return true})()""")
        assert ctx.eval("new UIEvent('mousedown').which===0&&new KeyboardEvent('keydown',{which:13}).which===13")
        for event_type in ['pointerdown', 'mousedown']:
            assert ctx.dispatch_pointer(event_type, x=40, y=25, bubbles=True,
                                        cancelable=True, button=0, buttons=1,
                                        pointerId=0, pointerType='mouse', isPrimary=True)
        assert ctx.eval('reads') == [['pointerdown', 0, 1, True], ['mousedown', 0, 1, True]]
        assert ctx.eval('state') == 'holding'
        ctx.advance(600, max_tasks=30)
        assert ctx.eval('state') == 'held'
        for event_type in ['pointerup', 'mouseup']:
            ctx.dispatch_pointer(event_type, x=40, y=25, bubbles=True,
                                 button=0, buttons=0, pointerType='mouse')
        assert ctx.eval('state') == 'held'
        ctx.eval("reads=[];state='idle';void 0")
        ctx.click('hold', hold_ms=600)
        assert ctx.eval('state') == 'held'
        assert ctx.eval('reads') == [
            ['pointerdown', 0, 1, True], ['mousedown', 0, 1, True],
            ['pointerup', 0, 1, True], ['mouseup', 0, 1, True], ['click', 0, 1, True],
        ]
        ctx.eval('reads=[];void 0')
        ctx.dispatch_pointer('mousedown', x=40, y=25, button=2, buttons=2)
        assert ctx.eval('reads') == [['mousedown', 2, 3, True]]
        print('ok native mouse/Pointer which, left-button hold, host click and family inheritance', flush=True)


if __name__ == '__main__':
    main()
