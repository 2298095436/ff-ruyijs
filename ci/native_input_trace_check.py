"""Opt-in native tracing preserves successful input and the original exceptions."""
import os

from ruyijs import Context, JSError


def run(enabled):
    previous = os.environ.get('RUYIJS_INPUT_TRACE')
    previous_tasks = os.environ.get('RUYIJS_TASK_TRACE')
    if enabled:
        os.environ['RUYIJS_INPUT_TRACE'] = '1'
        os.environ['RUYIJS_TASK_TRACE'] = '1'
    else:
        os.environ.pop('RUYIJS_INPUT_TRACE', None)
        os.environ.pop('RUYIJS_TASK_TRACE', None)
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
            try:
                ctx.eval("document.createElement('div').removeChild(document.createElement('span'))",
                         filename='native-trace-dom.js')
            except JSError as error:
                assert error.name == 'NotFoundError' and 'not a child' in error.message, str(error)
                assert 'native-trace-dom.js' in error.stack, error.stack
            else:
                raise AssertionError('Tracing changed an invalid removeChild operation')
            assert ctx.eval('6*7') == 42
        assert ctx.closed and ctx._process.returncode == 0
        stderr.seek(0)
        text = stderr.read().decode('utf-8', errors='replace')
        if enabled:
            assert 'ruyijs-input-phase phase=pointer-down' in text, text
            assert 'ruyijs-input-phase phase=done' in text, text
            assert 'ruyijs-native-failure' in text and 'callbacks.cpp' in text, text
            assert 'ruyijs-native-exception name=TypeError message=timer-kept-native-trace' in text, text
            assert 'ruyijs-dom-failure file=' in text and 'name=NotFoundError' in text, text
            assert 'ruyijs-task phase=callback boundary=begin' in text, text
            assert 'ruyijs-task phase=checkpoint boundary=end' in text, text
        else:
            assert all(marker not in text for marker in
                       ['ruyijs-input-', 'ruyijs-native-failure', 'ruyijs-native-exception',
                        'ruyijs-dom-failure', 'ruyijs-task']), text
        print('ok native input tracing', 'enabled' if enabled else 'disabled',
              'preserves input, original timer/eval exceptions and native shutdown', flush=True)
    finally:
        if stderr is not None:
            stderr.close()
        if previous is None:
            os.environ.pop('RUYIJS_INPUT_TRACE', None)
        else:
            os.environ['RUYIJS_INPUT_TRACE'] = previous
        if previous_tasks is None:
            os.environ.pop('RUYIJS_TASK_TRACE', None)
        else:
            os.environ['RUYIJS_TASK_TRACE'] = previous_tasks


if __name__ == '__main__':
    run(False)
    run(True)
