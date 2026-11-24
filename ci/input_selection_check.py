"""Native keyboard editing uses the original input's current selection."""
from ruyijs import Context


def read(ctx):
    return ctx.eval('[field.value,field.selectionStart,field.selectionEnd]')


def keyboard():
    with Context(timeout=15) as ctx:
        ctx.load_page('https://selection.test/', '<!doctype html><input id=field value="Tirana (TIA)">')
        ctx.eval('field.focus();field.setSelectionRange(0,field.value.length);void 0')
        assert read(ctx) == ['Tirana (TIA)', 0, 12]
        ctx.press('Backspace', target='field')
        assert read(ctx) == ['', 0, 0]
        ctx.type('Bordeaux', target='field', interval_ms=0)
        assert read(ctx) == ['Bordeaux', 8, 8]
        ctx.eval("field.setSelectionRange(2,5,'backward');void 0")
        ctx.type('X', target='field', interval_ms=0)
        assert read(ctx) == ['BoXaux', 3, 3]
        ctx.press('Backspace', target='field')
        assert read(ctx) == ['Boaux', 2, 2]
        ctx.eval('field.setSelectionRange(1,4);void 0')
        ctx.press('Backspace', target='field')
        assert read(ctx) == ['Bx', 1, 1]
        ctx.eval("field.addEventListener('beforeinput',e=>e.preventDefault());void 0")
        ctx.type('Y', target='field', interval_ms=0)
        ctx.press('Backspace', target='field')
        assert read(ctx) == ['Bx', 1, 1]
        print('ok native select-all replacement, caret insertion, selected deletion and cancellation', flush=True)


def api():
    with Context(timeout=15) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        ctx.load_page('https://selection.test/', '<!doctype html><input id=field>')
        for kind in ['text', 'search', 'tel', 'url', 'password']:
            ctx.set('kind', kind)
            assert ctx.eval("""(()=>{field.type=kind;field.value='abcdef';
field.setSelectionRange(2,4,'backward');return field.selectionStart===2&&
field.selectionEnd===4&&field.selectionDirection==='backward'})()""")
            assert ctx.eval("""(()=>{field.selectionStart=5;const a=field.selectionEnd===5;
field.selectionEnd=1;const b=field.selectionStart===1;
field.setSelectionRange(9,2);return a&&b&&field.selectionStart===2&&field.selectionEnd===2})()""")
            assert ctx.eval("""(()=>{field.setSelectionRange(1,3);field.value='abcdef';
const same=field.selectionStart===1&&field.selectionEnd===3;field.value='new';
return same&&field.selectionStart===3&&field.selectionEnd===3})()""")
        for kind in ['email', 'number', 'date', 'checkbox', 'radio', 'button', 'hidden']:
            ctx.set('kind', kind)
            assert ctx.eval("""(()=>{field.type=kind;let failures=0;
for(const f of [()=>field.setSelectionRange(0,1),()=>field.selectionStart=1,
()=>field.selectionEnd=1,()=>field.selectionDirection='backward',()=>field.setRangeText('x')])
try{f()}catch(e){if(e.name==='InvalidStateError')failures++}
return failures===5&&field.selectionStart===null&&field.selectionEnd===null&&field.selectionDirection===null})()""")
        ctx.eval("field.type='text';field.value='abcdef';field.setSelectionRange(4,6);void 0")
        ctx.eval("field.setRangeText('XYZ',1,3);void 0")
        assert read(ctx) == ['aXYZdef', 5, 7]
        ctx.eval("field.setSelectionRange(1,4);field.setRangeText('Q');void 0")
        assert read(ctx) == ['aQdef', 1, 2]
        for mode, expected in [('select', [1, 3]), ('start', [1, 1]), ('end', [3, 3])]:
            ctx.set('mode', mode)
            ctx.eval("field.value='abcde';field.setRangeText('ZZ',1,3,mode);void 0")
            assert read(ctx) == ['aZZde', *expected]
        assert ctx.eval("""(()=>{let range=false,type=false,missing=false;
try{field.setRangeText('x',3,1)}catch(e){range=e.name==='IndexSizeError'}
try{field.setRangeText('x',1,2,'bad')}catch(e){type=e instanceof TypeError}
try{field.setSelectionRange(1)}catch(e){missing=e instanceof TypeError}
return range&&type&&missing})()""")
        # A setter schedules a trusted select event; an unchanged selection does not.
        ctx.advance(1, max_tasks=128)
        ctx.eval("window.selected=[];field.addEventListener('select',e=>selected.push([e.isTrusted,e.bubbles]));field.setSelectionRange(0,1);void 0")
        assert ctx.eval('selected.length') == 0
        ctx.advance(1, max_tasks=128)
        assert ctx.eval('selected') == [[True, True]]
        ctx.eval('field.setSelectionRange(0,1);void 0')
        ctx.advance(1, max_tasks=128)
        assert ctx.eval('selected.length') == 1
        print('ok supported input types, endpoint clamping, range modes, errors and queued select', flush=True)


if __name__ == '__main__':
    keyboard()
    api()
