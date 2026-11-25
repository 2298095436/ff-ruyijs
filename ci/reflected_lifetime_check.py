"""Reflected facades retain their original identity through adoption and GC."""
from ruyijs import Context


def run(frame):
    with Context(timeout=20) as ctx:
        ctx.load_page('https://reflected.test/', '<!doctype html><iframe srcdoc="<body>child</body>"></iframe>')
        ctx.advance(10, max_tasks=100)
        source = ('document.querySelector("iframe").contentDocument' if frame else
                  'document.implementation.createHTMLDocument("source")')
        observed = ctx.eval('''(()=>{const source=''' + source + ''';
const element=source.createElement('div');source.body.appendChild(element);
const style=element.style,dataset=element.dataset;
style.color='red';dataset.value='original';
document.adoptNode(element);document.body.appendChild(element);
const first={style:element.style===style,dataset:element.dataset===dataset};
source.adoptNode(element);source.body.appendChild(element);
const second={style:element.style===style,dataset:element.dataset===dataset};
document.adoptNode(element);document.body.appendChild(element);
window.kept={element,style,dataset};
const svg=source.createElementNS('http://www.w3.org/2000/svg','svg');
source.body.appendChild(svg);const animated=svg.className;animated.baseVal='old';
document.adoptNode(svg);document.body.appendChild(svg);
window.keptSvg={svg,animated};
return {first,second,svg:svg.className===animated,color:element.style.color,
data:element.dataset.value,animated:svg.className.baseVal}})()''')
        assert observed == {'first': {'style': True, 'dataset': True},
                            'second': {'style': True, 'dataset': True},
                            'svg': True, 'color': 'red', 'data': 'original',
                            'animated': 'old'}, observed
        for _ in range(4):
            ctx.eval('''(()=>{for(let i=0;i<160;i++){
const source=document.implementation.createHTMLDocument('transient');
const e=source.createElement('p');source.body.appendChild(e);
e.style.opacity='0.5';e.dataset.value='temporary';
document.adoptNode(e);document.body.appendChild(e);
if(e.style.opacity!=='0.5'||e.dataset.value!=='temporary')throw Error('lost attribute');
e.remove();}
window.junk=Array.from({length:2000},(_,i)=>({i,text:'x'.repeat(80)}));})()''')
            ctx.collect_garbage()
            assert ctx.eval('''kept.element.style===kept.style && kept.element.dataset===kept.dataset &&
keptSvg.svg.className===keptSvg.animated && kept.style.color==='red' &&
kept.dataset.value==='original' && keptSvg.animated.baseVal==='old' ''')
        ctx.eval('kept.element.remove();keptSvg.svg.remove();kept=null;keptSvg=null;void 0')
        ctx.collect_garbage()
        assert ctx.eval('6*7') == 42
    assert ctx.closed and ctx._process.returncode == 0, ctx._process.returncode
    print('ok reflected facade identity, adoption, repeated GC and native shutdown:',
          'frame owner' if frame else 'inert document', flush=True)


if __name__ == '__main__':
    run(False)
    run(True)
