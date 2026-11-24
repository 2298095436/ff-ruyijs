"""Offline regression checks for Storage, module loading and form activation.

These tests execute the compiled runtime with no page shims or airline data.
They verify observable behavior and event order across script and host input.
"""
import sys

from ruyijs import Context


FAILURES = []
BASE = 'https://native-funnel.test/'


def check(name, condition, detail=''):
    print(('ok   ' if condition else 'FAIL ') + name, detail, flush=True)
    if not condition:
        FAILURES.append(name)


def storage():
    with Context(timeout=15) as ctx:
        ctx.load_page(BASE, '<!doctype html><title>storage</title>')
        value = ctx.eval("""(()=>{
          const s=localStorage;s.clear();s.setItem('alpha','one');s.beta='two';
          const before={alpha:s.alpha,beta:s.getItem('beta'),length:s.length,keys:Object.keys(s).sort()};
          delete s.alpha;
          const removed=s.getItem('alpha')===null;
          Object.defineProperty(s,'gamma',{value:3,enumerable:true,configurable:true,writable:true});
          const symbol=Symbol('extra');s[symbol]=42;
          const borrowed=Storage.prototype.getItem.call(s,'gamma');
          let invalid=false;try{Storage.prototype.getItem.call({},'gamma')}catch(e){invalid=e instanceof TypeError}
          return {before,removed,defined:s.getItem('gamma'),symbol:s[symbol],borrowed,invalid};
        })()""")
        check('Storage named reads and writes share the backing store',
              value.get('before') == {'alpha': 'one', 'beta': 'two', 'length': 2, 'keys': ['alpha', 'beta']}, value)
        check('Storage deletion, descriptors, symbols and borrowed brand checks',
              value.get('removed') and value.get('defined') == '3' and value.get('symbol') == 42
              and value.get('borrowed') == '3' and value.get('invalid'), value)
        ctx.put_resource(BASE + 'next', '<!doctype html><title>next</title>')
        ctx.navigate(BASE + 'next')
        check('Named Storage data survives same-origin navigation',
              ctx.eval("localStorage.beta==='two'&&localStorage.gamma==='3'&&!('alpha' in localStorage)"))
        ctx.eval("sessionStorage.token='session';void 0")
        check('Local and session areas stay independent', ctx.eval("localStorage.getItem('token')===null&&sessionStorage.getItem('token')==='session'"))
        ctx.eval('localStorage.clear();void 0')
        check('clear removes named properties', ctx.eval('localStorage.length===0&&Object.keys(localStorage).length===0'))


def modules():
    for name, markup, expected in [
        ('external', '<script type=module src=main.js></script>', 42),
        ('async external', '<script type=module async src=main.js></script>', 42),
        ('inline', '<script type=module>import {value} from "./dep.js";window.answer=value+2;window.metaURL=import.meta.url</script>', 42),
        ('inserted external', "<script>const s=document.createElement('script');s.type='module';s.src='main.js';document.head.appendChild(s)</script>", 42),
        ('inserted inline', "<script>const s=document.createElement('script');s.type='module';s.textContent='import {value} from \"./dep.js\";window.answer=value+2';document.head.appendChild(s)</script>", 42),
        ('two distinct inline modules', '<script type=module>window.answer=1</script><script type=module>window.answer+=1</script>', 2),
    ]:
        with Context(timeout=15) as ctx:
            ctx.configure_clock('logical', epoch_ms=1700000000000)
            ctx.put_resource(BASE + 'main.js', 'import {value} from "./dep.js";window.answer=value+2;window.currentScriptIsNull=document.currentScript===null',
                             headers=[['Content-Type', 'application/javascript']])
            ctx.put_resource(BASE + 'dep.js', 'export const value=40',
                             headers=[['Content-Type', 'application/javascript']])
            ctx.load_page(BASE, '<!doctype html><head>' + markup + '</head><body></body>')
            for _ in range(10):
                ctx.advance(10, max_tasks=50)
                if ctx.eval('window.answer!==undefined'):
                    break
            value = ctx.eval('window.answer??null')
            check(name + ' module executes its imports', value == expected, value)
            if name in ['external', 'async external', 'inserted external']:
                check(name + ' module has no currentScript', ctx.eval('window.currentScriptIsNull===true'))
            if name == 'inline':
                check('inline import.meta.url is the document URL', ctx.eval('metaURL') == BASE)


def forms():
    markup = '''<!doctype html><body><form id=form>
      <fieldset id=fieldset><input id=inside type=checkbox></fieldset>
      <input id=a name=choice type=radio checked><input id=b name=choice type=radio>
      <input id=box type=checkbox><input id=cancel type=checkbox>
      <input id=radioCancel name=choice type=radio>
      <script>
      window.events=[];
      for(const type of ['click','input','change'])document.querySelector('#box').addEventListener(type,e=>events.push([type,e.target.checked]));
      document.querySelector('#cancel').indeterminate=true;
      for(const id of ['cancel','radioCancel'])document.getElementById(id).addEventListener('click',e=>e.preventDefault());
      </script>'''
    with Context(timeout=15) as ctx:
        ctx.load_page(BASE, markup)
        check('fieldset.disabled reflects its boolean attribute', ctx.eval("(()=>{const f=document.querySelector('#fieldset');if(f.disabled)return false;f.disabled=true;return f.hasAttribute('disabled')&&f.disabled})()"))
        ctx.eval("document.querySelector('#inside').click();void 0")
        check('disabled fieldset suppresses child activation', ctx.eval("!document.querySelector('#inside').checked"))
        ctx.eval("document.querySelector('#b').click();void 0")
        check('radio click selects one member of its form group', ctx.eval("document.querySelector('#b').checked&&!document.querySelector('#a').checked"))
        ctx.eval("document.querySelector('#radioCancel').click();void 0")
        check('cancelled radio click restores the previously checked peer', ctx.eval("document.querySelector('#b').checked&&!document.querySelector('#radioCancel').checked"))
        ctx.eval("document.querySelector('#box').click();void 0")
        events = ctx.eval('events')
        check('click listeners see preactivation before input and change',
              events == [['click', True], ['input', True], ['change', True]], events)
        ctx.eval("document.querySelector('#cancel').click();void 0")
        check('cancelled checkbox restores checked and indeterminate', ctx.eval("!document.querySelector('#cancel').checked&&document.querySelector('#cancel').indeterminate"))
        ctx.eval('events=[];void 0')
        ctx.click("document.querySelector('#box')", hold_ms=0)
        events = ctx.eval('events')
        check('host click uses the same default activation and event order',
              events == [['click', False], ['input', False], ['change', False]], events)


def main():
    for name, action in [('storage', storage), ('modules', modules), ('forms', forms)]:
        try:
            action()
        except Exception as error:
            check(name + ' completed', False, str(error))
    if FAILURES:
        print('Failed:', ', '.join(FAILURES), flush=True)
        sys.exit(1)
    print('All native funnel regressions passed.', flush=True)


if __name__ == '__main__':
    main()
