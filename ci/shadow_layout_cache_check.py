"""Stable composed layouts reuse every scope and refresh after shadow CSSOM edits."""
import time

from ruyijs import Context


with Context(timeout=45) as ctx:
    ctx.configure_clock('system')
    rules = ''.join('.row{opacity:.5;--sample-' + str(i) + ':' + str(i) + ';}'
                    for i in range(120))
    rows = ''.join('<div class="row" data-i="' + str(i) + '">own</div>' for i in range(450))
    ctx.load_page('https://shadow-layout-cache.test/', '<!doctype html><style id="main">'
                  'html,body{margin:0}.row{width:120px;height:2px}#host,#second{width:96px}' + rules +
                  '</style><div id="rows">' + rows + '</div><div id="host"></div>')
    ctx.eval('''window.root=document.getElementById('host').attachShadow({mode:'closed'});
root.innerHTML='<style>div{width:40px;height:20px}</style><div></div>';
window.inner=root.querySelector('div');window.sheet=root.querySelector('style').sheet;void 0''')
    began = time.monotonic()
    observed = ctx.eval('''(()=>{const nodes=[...document.querySelectorAll('.row')];let sum=0;
for(let i=0;i<80;i++){const e=nodes[(i*7)%nodes.length];sum+=e.getBoundingClientRect().width;
sum+=parseFloat(getComputedStyle(e).width)}return {sum,hostHeight:host.getBoundingClientRect().height,
innerWidth:inner.getBoundingClientRect().width}})()''')
    elapsed = time.monotonic() - began
    assert observed == {'sum': 19200, 'hostHeight': 20, 'innerWidth': 40}, observed
    assert elapsed < 6, ('stable multi-scope layout exceeded 6s', elapsed)
    print('ok 160 stable geometry/computed measurements with a closed-shadow scope:',
          round(elapsed, 3), 'seconds', flush=True)

    observed = ctx.eval('''(()=>{sheet.insertRule('div{width:60px;height:30px}',sheet.cssRules.length);
const edited=[host.getBoundingClientRect().height,inner.getBoundingClientRect().width];
sheet.disabled=true;const disabled=[host.getBoundingClientRect().height,inner.getBoundingClientRect().width];
const adopted=new CSSStyleSheet();adopted.replaceSync('div{width:70px;height:25px}');
root.adoptedStyleSheets=[adopted];const first=host.getBoundingClientRect().height;
adopted.replaceSync('div{width:90px;height:35px}');const second=host.getBoundingClientRect().height;
const replacedWidth=inner.getBoundingClientRect().width;root.adoptedStyleSheets=[];
const removed=host.getBoundingClientRect().height;sheet.disabled=false;
const restored=[host.getBoundingClientRect().height,inner.getBoundingClientRect().width];
return {edited,disabled,first,second,replacedWidth,removed,restored}})()''')
    assert observed == {'edited': [30, 60], 'disabled': [0, 96], 'first': 25,
                        'second': 35, 'replacedWidth': 90, 'removed': 0,
                        'restored': [30, 60]}, observed
    print('ok shadow CSSOM insert/disabled and adopted-sheet replacement refresh document callers', flush=True)

    observed = ctx.eval('''(()=>{const second=document.createElement('div');second.id='second';document.body.appendChild(second);
const root2=second.attachShadow({mode:'closed'});root2.innerHTML='<style>div{width:80px;height:15px}</style><div></div>';
const child=root2.querySelector('div'),style=root2.querySelector('style').sheet;
const before=[second.getBoundingClientRect().height,child.getBoundingClientRect().width];
style.cssRules[0].style.height='45px';const edited=second.getBoundingClientRect().height;
// Declare the same value before detachment: this control tests scope removal,
// independently of whether detached CSSOM-only declarations are retained.
root2.querySelector('style').textContent='div{width:80px;height:45px}';
second.remove();const light=document.querySelector('.row').getBoundingClientRect().width;
document.body.appendChild(second);const reconnected=second.getBoundingClientRect().height;
const nested=child.attachShadow({mode:'closed'});nested.innerHTML='<style>span{display:block;width:55px;height:12px}</style><span></span>';
const span=nested.querySelector('span'),nestedSheet=nested.querySelector('style').sheet;
const nestedBefore=span.getBoundingClientRect().width;
nestedSheet.cssRules[0].style.width='65px';void host.getBoundingClientRect().height;
const nestedAfter=span.getBoundingClientRect().width;
document.getElementById('main').sheet.insertRule('.row{width:130px}',document.getElementById('main').sheet.cssRules.length);
return {before,edited,light,reconnected,nestedBefore,nestedAfter,
mainWidth:document.querySelector('.row').getBoundingClientRect().width,
firstShadowWidth:inner.getBoundingClientRect().width}})()''')
    assert observed == {'before': [15, 80], 'edited': 45, 'light': 120, 'reconnected': 45,
                        'nestedBefore': 55, 'nestedAfter': 65, 'mainWidth': 130,
                        'firstShadowWidth': 60}, observed
    assert not ctx.net_log()
    print('ok scope addition, removal/reconnect, nested closed roots and document CSSOM stay live', flush=True)

    observed = ctx.eval('''(()=>{const moved=document.createElement('div');moved.className='row';
const host3=document.createElement('section');host3.style.width='96px';document.body.appendChild(host3);
host3.appendChild(moved);const light=moved.getBoundingClientRect().width;
const shadow=host3.attachShadow({mode:'closed'});shadow.innerHTML='<style>div{width:75px;height:10px}</style>';
shadow.appendChild(moved);const entered=moved.getBoundingClientRect().width;
shadow.removeChild(moved);document.getElementById('rows').appendChild(moved);
const left=moved.getBoundingClientRect().width;root.appendChild(moved);
const other=moved.getBoundingClientRect().width;return {light,entered,left,other}})()''')
    assert observed == {'light': 130, 'entered': 75, 'left': 130, 'other': 60}, observed
    print('ok moving retained elements across existing/new scopes never reuses the old cascade', flush=True)
assert ctx.closed and ctx._process.returncode == 0, ctx._process.returncode
