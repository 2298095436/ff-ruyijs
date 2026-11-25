"""Retained NamedNodeMaps stay live without rebuilding for unrelated mutations."""
import time

from ruyijs import Context


with Context(timeout=45) as ctx:
    ctx.configure_clock('system')
    ctx.load_page('https://attribute-map-scaling.test/', '<!doctype html><div id="target"></div>' +
                  '<div class="row" data-a="a" data-b="b" data-c="c" data-d="d"></div>' * 2000)
    ctx.eval('window.nodes=[...document.querySelectorAll(".row")];'
             'window.maps=nodes.map(e=>e.attributes);void 0')
    start = time.monotonic()
    observed = ctx.eval('''(()=>{for(let i=0;i<600;i++)target.setAttribute('data-tick',String(i));
for(let i=0;i<100;i++){const e=document.createElement('span');target.appendChild(e);e.remove()}
return {maps:maps.length,kept:maps[0]['data-a'].value,last:target.getAttribute('data-tick'),
firstCount:maps[0].length,lastCount:maps[maps.length-1].length}})()''')
    elapsed = time.monotonic() - start
    assert observed == {'maps': 2000, 'kept': 'a', 'last': '599',
                        'firstCount': 5, 'lastCount': 5}, observed
    assert elapsed < 6, ('unrelated mutations rebuilt retained attribute maps', elapsed)
    print('ok 2000 retained attribute maps / 600 attribute writes / 200 tree edits:',
          round(elapsed, 3), 'seconds', flush=True)

    observed = ctx.eval('''(()=>{const e=nodes[0],map=maps[0],kept=map['data-a'];
e.setAttribute('data-a','updated');const same=map['data-a']===kept&&kept.value==='updated';
e.setAttribute('style','width:1px');const style=map.style;
e.style.width='2px';const styleLive=map.style===style&&style.value.includes('2px');
e.removeAttribute('style');const styleRemoved=map.style===undefined&&map.getNamedItem('style')===null;
e.setAttribute('data-added','new');e.removeAttribute('data-b');
const names=Array.from(map,a=>a.name);
e.setAttributeNS('urn:own:map','p:marked','v');
e.removeAttributeNS('urn:own:map','marked');e.setAttributeNS('urn:own:map','q:marked','v');
const renamed=map['p:marked']===undefined&&map['q:marked']===map[map.length-1]&&map['q:marked'].name==='q:marked';
e.removeAttributeNS('urn:own:map','marked');
return {same,styleLive,styleRemoved,names,renamed,removed:map['q:marked']===undefined}})()''')
    assert observed == {'same': True, 'styleLive': True, 'styleRemoved': True,
                        'names': ['class', 'data-a', 'data-c', 'data-d', 'data-added'],
                        'renamed': True, 'removed': True}, observed
    print('ok live Attr values, index/name membership, style and namespaced attribute replacement', flush=True)

    observed = ctx.eval('''(()=>{const e=nodes[1],map=maps[1];
e.setAttributeNS('urn:own:map','p:UPPER','v');const html=map['p:UPPER']===undefined;
const xml=document.implementation.createDocument(null,'root');xml.documentElement.appendChild(xml.adoptNode(e));
const foreign=map===e.attributes&&map['p:UPPER']===map[map.length-1]&&map['p:UPPER'].value==='v';
document.body.appendChild(document.adoptNode(e));const returned=map===e.attributes&&map['p:UPPER']===undefined;
e.remove();e.setAttribute('detached','yes');const detached=map.detached.value;
e.removeAttribute('detached');document.body.appendChild(e);
return {html,foreign,returned,detached,removed:map.detached===undefined}})()''')
    assert observed == {'html': True, 'foreign': True, 'returned': True,
                        'detached': 'yes', 'removed': True}, observed
    print('ok held maps follow HTML/XML adoption and detached element changes', flush=True)

    observed = ctx.eval('''(()=>{const ns='http://www.w3.org/2000/svg';
const svg=document.createElementNS(ns,'svg'),polygon=document.createElementNS(ns,'polygon'),rect=document.createElementNS(ns,'rect');
document.body.appendChild(svg);svg.append(polygon,rect);
const a=svg.attributes,b=polygon.attributes,c=rect.attributes;
svg.viewBox.baseVal.width=7;polygon.points.appendItem(svg.createSVGPoint());rect.width.baseVal.value=8;
return {viewBox:a.getNamedItem('viewBox')?.value,points:b.getNamedItem('points')?.value,
width:c.getNamedItem('width')?.value,counts:[a.length,b.length,c.length]}})()''')
    assert observed == {'viewBox': '0 0 7 0', 'points': '0,0', 'width': '8',
                        'counts': [1, 1, 1]}, observed
    assert not ctx.net_log()
    print('ok typed SVG viewBox, points and length writes update held attribute maps', flush=True)
assert ctx.closed and ctx._process.returncode == 0, ctx._process.returncode
