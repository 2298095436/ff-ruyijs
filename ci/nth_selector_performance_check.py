"""Position selectors scale across a stable read and refresh after DOM changes."""
import time

from ruyijs import Context


with Context(timeout=40) as ctx:
    rules = ''.join('.bench > .row:nth-child(odd){opacity:0.5;--rule' + str(i) +
                    ':' + str(i) + ';}' for i in range(400))
    rows = ''.join('<' + ('i' if i % 2 == 0 else 'b') +
                   ' class="row' + (' selected' if i % 3 == 0 else '') +
                   '" data-n="' + str(i) + '"><span>row</span></' +
                   ('i' if i % 2 == 0 else 'b') + '>' for i in range(900))
    html = '<!doctype html><style>' + rules + '</style><div id="list" class="bench">' + rows + '</div>'
    start = time.monotonic()
    ctx.load_page('https://nth-selector.test/', html)
    elapsed = time.monotonic() - start
    assert elapsed < 8, ('position selector load exceeded 8s', elapsed)
    observed = ctx.eval("""(()=>{const rows=[...document.querySelectorAll('#list>.row')];
return {odd:document.querySelectorAll('#list>.row:nth-child(odd)').length,
reverse:document.querySelector('#list>.row:nth-last-child(1)').dataset.n,
typed:[...document.querySelectorAll('#list>.row:nth-of-type(2)')].map(e=>e.dataset.n),
lastTyped:[...document.querySelectorAll('#list>.row:nth-last-of-type(1)')].map(e=>e.dataset.n),
filtered:document.querySelectorAll('#list>.row:nth-child(odd of .selected)').length,
opacity:[getComputedStyle(rows[0]).opacity,getComputedStyle(rows[1]).opacity]}})()""")
    assert observed == {'odd': 450, 'reverse': '899', 'typed': ['2', '3'],
                        'lastTyped': ['898', '899'], 'filtered': 150,
                        'opacity': ['0.5', '1']}, observed
    print('ok 900 elements / 400 position rules load within 8s:', round(elapsed, 3), flush=True)
    observed = ctx.eval("""(()=>{const list=document.getElementById('list'),first=list.firstElementChild;
const held=getComputedStyle(first);const added=document.createElement('em');added.className='row';
list.insertBefore(added,first);list.insertBefore(document.createTextNode(' '),first);
list.insertBefore(document.createComment('ignored'),first);
const shifted=held.opacity,odd=document.querySelectorAll('#list>.row:nth-child(odd)').length;
added.remove();const restored=held.opacity;first.classList.remove('selected');
const filtered=document.querySelector('#list>.row:nth-child(odd of .selected)').dataset.n;
list.appendChild(first);const moved=held.opacity;
return {shifted,odd,restored,filtered,moved,last:document.querySelector('#list>.row:nth-last-child(1)').dataset.n}})()""")
    assert observed == {'shifted': '1', 'odd': 451, 'restored': '0.5',
                        'filtered': '3', 'moved': '1', 'last': '0'}, observed
    print('ok live computed styles and child/type/filter positions after insert, remove and move', flush=True)
    observed = ctx.eval("""(()=>{const host=document.createElement('div');document.body.appendChild(host);
const root=host.attachShadow({mode:'closed'});root.innerHTML='<style>section>span:nth-child(2){opacity:0.25}</style><section><span></span><span></span></section>';
const section=root.querySelector('section'),target=section.lastElementChild,held=getComputedStyle(target);
const before=held.opacity;section.insertBefore(document.createElement('span'),section.firstElementChild);
const after=held.opacity;return {before,after}})()""")
    assert observed == {'before': '0.25', 'after': '1'}, observed
    assert ctx.eval('6*7') == 42
    print('ok position memo is rebuilt for connected closed-shadow mutations', flush=True)
assert ctx.closed and ctx._process.returncode == 0, ctx._process.returncode
