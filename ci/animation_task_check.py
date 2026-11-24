"""Replacing animation boundaries removes their original native queue tasks."""
from ruyijs import Context


def css_boundaries():
    with Context(timeout=20) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-tasks.test/css', '''<!doctype html><style>
@keyframes pulse {to {opacity:.5}} #bar {animation:pulse 1s infinite}
</style><div id=bar></div><script>
window.events=[];
for(const type of ['animationstart','animationiteration','animationcancel'])
bar.addEventListener(type,e=>events.push([e.type,e.elapsedTime,e.isTrusted]));
</script>''')
        assert ctx.eval('bar.getAnimations().length') == 1
        initial = ctx.advance(0, max_tasks=1000)
        for batch in range(3):
            ctx.eval('''window.updates=0;window.task=setInterval(()=>{
bar.style.width=(++updates)+'px';if(updates===50)clearInterval(task)},5);void 0''')
            state = ctx.advance(250, max_tasks=1000)
            assert ctx.eval('updates') == 50
            assert state['pending'] <= initial['pending'] + 1, (batch, initial, state)
        rows = ctx.eval('events')
        assert rows == [['animationstart', 0, True]], rows
        ctx.eval("bar.style.animationDuration='2s';void 0")
        assert ctx.advance(0, max_tasks=1000)['pending'] <= 2
        ctx.advance(1250, max_tasks=1000)
        rows = ctx.eval('events')
        assert rows == [['animationstart', 0, True], ['animationiteration', 2, True]], rows
        ctx.eval("bar.style.animation='none';void 0")
        assert ctx.advance(0, max_tasks=1000)['pending'] == 0
        rows = ctx.eval('events')
        assert [r[0] for r in rows] == ['animationstart', 'animationiteration', 'animationcancel'], rows
        print('ok CSS style updates retain one boundary; duration changes and cancellation remove stale tasks', flush=True)


def script_boundaries():
    with Context(timeout=20) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-tasks.test/script', '<!doctype html><div id=bar></div>')
        ctx.eval('''window.a=bar.animate([{opacity:0},{opacity:1}],1000);
window.finished=0;window.finishEvents=0;a.finished.then(()=>finished++);
a.onfinish=()=>finishEvents++;void 0''')
        ctx.advance(0, max_tasks=1000)
        ctx.eval('''for(let i=0;i<150;i++){
a.effect.updateTiming({duration:1000+i});a.currentTime=10;}void 0''')
        state = ctx.advance(0, max_tasks=1000)
        assert state['pending'] == 1, state
        ctx.advance(1200, max_tasks=1000)
        assert ctx.eval('[finished,finishEvents]') == [1, 1]
        assert ctx.advance(0, max_tasks=1000)['pending'] == 0
        ctx.eval('''window.userTimerFired=false;setTimeout(()=>userTimerFired=true,600);
a.play();a.pause();a.play();a.pause();a.play();a.cancel();void 0''')
        assert ctx.advance(0, max_tasks=1000)['pending'] == 1
        assert ctx.eval('userTimerFired') is False
        ctx.advance(600, max_tasks=1000)
        assert ctx.eval('userTimerFired') is True
        assert ctx.advance(0, max_tasks=1000)['pending'] == 0
        print('ok script timing updates, repeated play/pause and cancel leave no obsolete boundary tasks', flush=True)


if __name__ == '__main__':
    css_boundaries()
    script_boundaries()
