"""Debug logs observe native iframe APIs, including cross-realm input listeners."""
from ruyijs import Context


HTML = '''<!doctype html><style>html,body{margin:0}
#host{position:fixed;left:20px;top:30px;width:200px;height:50px}
</style><div id=host></div><script>
window.events=[];const shadow=host.attachShadow({mode:'closed'}),
frame=document.createElement('iframe');
frame.style.cssText='width:200px;height:50px;border:0';shadow.append(frame);
const doc=frame.contentDocument;doc.open();doc.write(
'<!doctype html><style>html,body{margin:0}#button,#inner{width:180px;height:40px}</style>'+
'<div id=button role=button><div id=inner>hold</div></div>');doc.close();
doc.querySelector('#button').addEventListener('mousedown',e=>events.push({
 type:e.type,id:e.target.id,trusted:e.isTrusted,x:e.clientX}));
</script>'''


def check(mode):
    with Context(timeout=15, mode=mode) as ctx:
        ctx.configure_clock('logical', epoch_ms=1700000000000)
        for navigation in range(2):
            url = f'https://monitor.test/{navigation}'
            if navigation:
                ctx.put_resource(url, HTML)
                ctx.navigate(url)
            else:
                ctx.load_page(url, HTML)
            for _ in range(5):
                ctx.advance(10, max_tasks=50)
            # Child Window/Document reads use the same monitor as parent APIs.
            ctx.get_api_log()
            ctx.eval("frames.length;void 0")
            assert ctx.dispatch_pointer('mousedown', x=100, y=50,
                                        bubbles=True, cancelable=True,
                                        button=0, buttons=1)
            assert ctx.eval('events') == [{'type': 'mousedown', 'id': 'inner',
                                          'trusted': True, 'x': 80}]
            rows = ctx.get_api_log()
            if mode == 'debug':
                members = {row['p'] for row in rows}
                assert {'Event.type', 'Event.target', 'Event.isTrusted',
                        'MouseEvent.clientX'} <= members, rows
            else:
                assert rows == [], rows
        # Retired child monitor ports must clear before the monitor is freed.
        ctx.eval('host.remove();void 0')
        ctx.get_api_log()
    print('ok iframe event access monitor across navigation and retirement: ' + mode,
          flush=True)


if __name__ == '__main__':
    check('debug')
    check('default')
