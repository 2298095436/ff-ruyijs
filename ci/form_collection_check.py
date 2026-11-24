"""Live form collections stay correct without rescanning on unrelated DOM work."""
import time

from ruyijs import Context


def semantics():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://forms.test/', '''<!doctype html><form id=f>
<input id=a name=alpha><input id=r1 type=radio name=group value=one>
<input id=r2 type=radio name=group value=two></form>
<input id=external name=outside form=f><div id=updates></div>''')
        assert ctx.eval('''(()=>{window.outsideControl=document.getElementById('external');
window.list=f.elements;window.group=list.namedItem('group');
return list.length===4&&list[0]===a&&list.alpha===a&&f.alpha===a&&group.length===2})()''')
        assert ctx.eval('''(()=>{const n=document.createElement('input');n.id='b';n.name='beta';
f.append(n);a.name='renamed';r1.remove();return list===f.elements&&list.length===4&&
list[3]===outsideControl&&list.namedItem('alpha')===null&&f.alpha===undefined&&
list.renamed===a&&f.renamed===a&&group.length===1&&group[0]===r2&&f.beta===b})()''')
        assert ctx.eval('''(()=>{const form=f;form.id='other';return list.length===3&&
list.namedItem('outside')===null&&form.outside===undefined})()''')
        assert ctx.eval('''(()=>{const form=document.querySelector('form');form.id='f';
return list.length===4&&list.namedItem('outside')===outsideControl&&form.outside===outsideControl})()''')
        assert ctx.eval('''(()=>{const form=document.querySelector('form');
Object.defineProperty(form,'beta',{value:'user',configurable:true});b.name='gamma';
return form.beta==='user'&&form.gamma===b&&list.gamma===b&&list.beta===undefined})()''')
        ctx.eval("group.value='two';void 0")
        assert ctx.eval('group.value') == 'two'
        assert ctx.eval('''(()=>{const n=document.createElement('input');n.type='radio';
n.name='group';n.id='r3';n.value='three';f.append(n);return group.length===2&&group[1]===n})()''')
        assert ctx.eval('''(()=>{const n=document.createElement('input');n.id='last';
f.append(n);return f[4]===n&&f.length===6&&f.last===n&&list[4]===n&&
Object.keys(list).filter(x=>/^[0-9]+$/.test(x)).length===6})()''')
        print('ok held form/radio collections, names, external ownership and user overrides', flush=True)


def mutation_cost():
    with Context(timeout=20) as ctx:
        ctx.load_page('https://forms.test/', '<!doctype html><body><div id=updates></div>')
        ctx.eval('''window.held=[];for(let i=0;i<30;i++){const f=document.createElement('form');
f.innerHTML='<input name="field"><input name="choice" type="radio" value="yes">';
document.body.append(f);held.push(f.elements)};void 0''')
        # Typical autocomplete work: many non-control options and attributes,
        # with live form collections held by application/instrumentation code.
        start = time.monotonic()
        ctx.eval('''for(let i=0;i<1400;i++){const option=document.createElement('div');
option.setAttribute('data-option',String(i));option.textContent='Airport '+i;
updates.append(option)};void 0''')
        elapsed = time.monotonic() - start
        assert ctx.eval('held.every(x=>x.length===2&&x.field.name==="field")')
        print('ok 1400 unrelated option mutations with 30 held form collections:',
              round(elapsed, 3), 'seconds', flush=True)


if __name__ == '__main__':
    semantics()
    mutation_cost()
