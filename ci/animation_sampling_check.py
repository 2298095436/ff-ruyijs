"""Animation sampling preserves CSS dependencies without scanning for every width tick."""
from time import monotonic

from ruyijs import Context


KEYFRAMES = '@keyframes pulse {to {opacity:.5}}'


def dimension_updates():
    with Context(timeout=20) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-sampling.test/large', '''<!doctype html><style>
.row {display:block;padding:1px;color:#123456}
</style><div id=bar style="width:0px"></div>''' +
                      '<div class=row>ordinary text</div>' * 2000)
        ctx.eval('''window.updates=0;window.task=setInterval(()=>{
bar.style.width=(++updates)+'px';if(updates===200)clearInterval(task)},1);void 0''')
        start = monotonic()
        state = ctx.advance(1000, max_tasks=2000, max_wall_ms=1000)
        elapsed = monotonic() - start
        assert ctx.eval('updates') == 200, (state, elapsed, ctx.eval('updates'))
        assert state['pending'] == 0 and not state['exhausted'], state
        print('ok 200 dimension updates on 2000 elements finish within a 1000ms native budget:',
              round(elapsed, 3), flush=True)


def style_dependencies():
    for selector, target in [('#bar[style*="60px"]', 'bar'),
                              ('#host:has([style*="60px"]) #watch', 'watch')]:
        with Context(timeout=15) as ctx:
            ctx.configure_clock('logical', epoch_ms=1700000000000)
            ctx.load_page('https://animation-sampling.test/selector',
                          '<!doctype html><style>' + KEYFRAMES + selector +
                          '{animation:pulse .02s}</style>' +
                          '<div id=host><div id=bar style="width:40px"></div><div id=watch></div></div>' +
                          '<script>window.ended=[];document.addEventListener("animationend",e=>ended.push(e.target.id))</script>')
            assert ctx.eval(target + '.getAnimations().length') == 0
            ctx.eval("bar.style.width='60px';void 0")
            ctx.advance(50, max_tasks=1000)
            assert ctx.eval('ended') == [target], (selector, ctx.eval('ended'))
    print('ok raw style attribute selectors and :has() still react to dimension changes', flush=True)

    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-sampling.test/shadow', '<!doctype html><div id=host></div>')
        ctx.eval('''window.root=host.attachShadow({mode:'closed'});
root.innerHTML='<style>@keyframes pulse {to {opacity:.5}} div[style*="60px"]{animation:pulse .02s}</style><div id=bar style="width:40px"></div>';
window.shadowBar=root.querySelector('#bar');window.ended=0;
shadowBar.addEventListener('animationend',()=>ended++);void 0''')
        assert ctx.eval('shadowBar.getAnimations().length') == 0
        ctx.eval("shadowBar.style.width='60px';void 0")
        ctx.advance(50, max_tasks=1000)
        assert ctx.eval('ended') == 1
    print('ok style dependency detection includes closed shadow cascade scopes', flush=True)

    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-sampling.test/cssom', '<!doctype html><style>' +
                      KEYFRAMES + '</style><div id=bar style="width:40px"></div>' +
                      '<script>window.ended=0;bar.addEventListener("animationend",()=>ended++)</script>')
        assert ctx.eval('bar.getAnimations().length') == 0
        ctx.eval('''document.styleSheets[0].insertRule('#bar[style*="60px"]{animation:pulse .02s}',1);
bar.style.width='60px';void 0''')
        ctx.advance(50, max_tasks=1000)
        assert ctx.eval('ended') == 1
        ctx.eval("bar.style.width='40px';void 0")
        assert ctx.eval('bar.getAnimations().length') == 0
    print('ok CSSOM rule insertion refreshes the style dependency before subsequent width changes', flush=True)


def animation_inputs():
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://animation-sampling.test/inputs', '<!doctype html><style>' +
                      KEYFRAMES + '#bar{animation:pulse var(--speed)}</style>' +
                      '<div id=bar style="--speed:.1s"></div>')
        assert ctx.eval('bar.getAnimations()[0].effect.getTiming().duration') == 100
        ctx.advance(0, max_tasks=1000)
        ctx.eval("bar.style.setProperty('--speed','.2s');void 0")
        assert ctx.eval('bar.getAnimations()[0].effect.getTiming().duration') == 200
        ctx.eval("bar.style.animationDuration='.3s';void 0")
        assert ctx.eval('bar.getAnimations()[0].effect.getTiming().duration') == 300
        ctx.eval("bar.style.display='none';void 0")
        assert ctx.eval('bar.getAnimations().length') == 0
        ctx.advance(0, max_tasks=1000)
    print('ok custom properties, animation duration and display changes remain animation inputs', flush=True)


if __name__ == '__main__':
    dimension_updates()
    style_dependencies()
    animation_inputs()
