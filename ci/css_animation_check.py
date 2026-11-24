"""CSS animations deliver native lifecycle events that can close real dialogs.

The airline's welcome modal waits for animationend after adding its closing
class. This fixture covers that generic pattern, multiple named animations,
delays, iterations, pause/resume, cancellation and absent keyframes offline.
"""
from ruyijs import Context


MARKUP = '''<!doctype html><style>
@keyframes fade { from {opacity:1} to {opacity:0} }
@keyframes slide { from {transform:translateY(0)} to {transform:translateY(20px)} }
.closing {animation: 0.07s cubic-bezier(.68,-.55,.265,1.55) forwards slide, .02s forwards fade}
.repeat {animation: fade 0.02s 0.01s 2}
.paused {animation: fade 0.04s paused}
.missing {animation: unknown 0.01s}
.cancel {animation: fade 1s}
</style><dialog id=modal open>test</dialog><div id=repeat></div><div id=paused></div>
<div id=missing></div><div id=cancel></div><script>
window.events=[];
for(const type of ['animationstart','animationiteration','animationend','animationcancel'])
document.addEventListener(type,e=>events.push({type:e.type,id:e.target.id,name:e.animationName,
  elapsed:e.elapsedTime,trusted:e.isTrusted,typed:e instanceof AnimationEvent,
  bubbles:e.bubbles,pseudo:e.pseudoElement}));
modal.addEventListener('animationend',e=>{if(e.animationName==='slide')modal.close()});
</script>'''


def advance(ctx, ms):
    ctx.advance(ms, max_tasks=1000)


def main():
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://css-animation.test/', MARKUP)
        ctx.eval("modal.className='closing';void 0")
        state = ctx.eval("modal.getAnimations().map(a=>({name:a.animationName,typed:a instanceof CSSAnimation,duration:a.effect.getTiming().duration}))")
        assert len(state) == 2 and all(a['typed'] for a in state), state
        assert {a['name'] for a in state} == {'slide', 'fade'}, state
        advance(ctx, 100)
        state = ctx.eval('({open:modal.open,events:events.filter(e=>e.id==="modal")})')
        assert state['open'] is False, state
        ended = [e for e in state['events'] if e['type'] == 'animationend']
        assert [(e['name'], round(e['elapsed'], 3)) for e in ended] == [('fade', .02), ('slide', .07)], state
        assert all(e['trusted'] and e['typed'] and e['bubbles'] and e['pseudo'] == '' for e in state['events']), state
        print('ok CSS-created animations close a dialog through typed trusted animationend events', flush=True)

        ctx.eval("document.querySelector('#repeat').className='repeat';void 0")
        advance(ctx, 80)
        rows = ctx.eval("events.filter(e=>e.id==='repeat')")
        assert [r['type'] for r in rows] == ['animationstart', 'animationiteration', 'animationend'], rows
        assert [round(r['elapsed'], 3) for r in rows] == [0, .02, .04], rows
        print('ok delay, iteration and final active elapsed times', flush=True)

        ctx.eval("document.querySelector('#paused').className='paused';void 0")
        advance(ctx, 100)
        assert ctx.eval("document.querySelector('#paused').getAnimations()[0].playState") == 'paused'
        assert not ctx.eval("events.some(e=>e.id==='paused'&&e.type==='animationend')")
        ctx.eval("document.querySelector('#paused').style.animationPlayState='running';void 0")
        advance(ctx, 100)
        assert ctx.eval("events.some(e=>e.id==='paused'&&e.type==='animationend')")
        print('ok CSS play-state pauses and resumes the original animation', flush=True)

        ctx.eval("document.querySelector('#cancel').className='cancel';void 0")
        advance(ctx, 20)
        ctx.eval("document.querySelector('#cancel').className='';void 0")
        advance(ctx, 20)
        assert ctx.eval("events.some(e=>e.id==='cancel'&&e.type==='animationcancel')")
        assert not ctx.eval("events.some(e=>e.id==='cancel'&&e.type==='animationend')")
        ctx.eval("document.querySelector('#missing').className='missing';void 0")
        advance(ctx, 50)
        assert ctx.eval("document.querySelector('#missing').getAnimations().length") == 0
        print('ok removed CSS animation cancels and missing keyframes create no animation', flush=True)

        ctx.eval("window.wa=document.querySelector('#missing').animate([{opacity:0},{opacity:1}],10);window.waDone=false;wa.finished.then(()=>waDone=true);void 0")
        advance(ctx, 40)
        assert ctx.eval('waDone')
        print('ok script-created Web Animations keep their existing finished promise behavior', flush=True)


if __name__ == '__main__':
    main()
