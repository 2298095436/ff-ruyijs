"""Opt-in native tracing preserves successful input and the original exceptions."""
import os

from ruyijs import Context, JSError


def run(enabled):
    previous = os.environ.get('RUYIJS_INPUT_TRACE')
    if enabled:
        os.environ['RUYIJS_INPUT_TRACE'] = '1'
    else:
        os.environ.pop('RUYIJS_INPUT_TRACE', None)
    stderr = None
    try:
        with Context(timeout=15) as ctx:
            stderr = os.fdopen(os.dup(ctx._stderr.fileno()), 'rb')
            ctx.configure_clock('logical', epoch_ms=1700000000000)
            ctx.load_page('https://native-trace.test/', '''<!doctype html><style>
html,body{margin:0}button{width:100px;height:50px;border:0;padding:0}
</style><button id=button>click</button><script>window.clicked=0;button.onclick=()=>clicked++;</script>''')
            report = ctx.click_at(x=20, y=20, hold_ms=10, diagnostics=True)
            assert report['delivered'] and report['heldMs'] == 10 and ctx.eval('clicked') == 1, report
            ctx.eval("setTimeout(()=>{throw new TypeError('timer-kept-native-trace')},0);void 0")
            try:
                ctx.advance(10, max_tasks=100)
            except JSError as error:
                assert 'TypeError' in str(error) and 'timer-kept-native-trace' in str(error), str(error)
            else:
                raise AssertionError('Tracing swallowed the original timer exception')
            try:
                ctx.eval("throw new RangeError('eval-kept-native-trace')")
            except JSError as error:
                assert 'RangeError' in str(error) and 'eval-kept-native-trace' in str(error), str(error)
            else:
                raise AssertionError('Tracing swallowed the original eval exception')
            assert ctx.eval('6*7') == 42
        assert ctx.closed and ctx._process.returncode == 0
        stderr.seek(0)
        text = stderr.read().decode('utf-8', errors='replace')
        if enabled:
            assert 'ruyijs-input-phase phase=pointer-down' in text, text
            assert 'ruyijs-input-phase phase=done' in text, text
            assert 'ruyijs-native-failure' in text and 'callbacks.cpp' in text, text
        else:
            assert 'ruyijs-input-' not in text and 'ruyijs-native-failure' not in text, text
        print('ok native input tracing', 'enabled' if enabled else 'disabled',
              'preserves input, original timer/eval exceptions and native shutdown', flush=True)
    finally:
        if stderr is not None:
            stderr.close()
        if previous is None:
            os.environ.pop('RUYIJS_INPUT_TRACE', None)
        else:
            os.environ['RUYIJS_INPUT_TRACE'] = previous


if __name__ == '__main__':
    run(False)
    run(True)
