"""Local resource-only browser compatibility checks for the built wheel."""
import json
from pathlib import Path
import sys
from ruyijs import Context

def runtime_cases():
    cases = []
    def check(name, script, expected, html='<title>Fixture</title>', resources=None, settle=0):
        cases.append((name,script,expected,html,resources,settle))
    check('html_entity_script_url','({runs:window.runs,urls:performance.getEntriesByType("resource").filter(e=>e.name.includes("/app.js")).map(e=>e.name)})',
        {'runs':1,'urls':['https://fixture.test/app.js?a=1&b=2']},
        '<title>Fixture</title><script src="/app.js?a=1&amp;b=2"></script>',
        [('https://fixture.test/app.js?a=1&b=2','window.runs=(window.runs||0)+1','application/javascript')])
    check('character_data_layout_invalidation',r'''(() => {
      const e=document.querySelector('#s'),t=e.firstChild;
      const before=e.getBoundingClientRect().width;t.data='WWWWWWWWWWWW';
      const after=e.getBoundingClientRect().width;
      return {text:e.textContent,grew:after>before};})()''',
      {'text':'WWWWWWWWWWWW','grew':True},'<title>Fixture</title><span id="s" style="display:inline-block;font:20px monospace">i</span>')
    check('inner_text_excludes_script','document.body.innerText.includes("LEAK_SENTINEL")',False,
      '<title>Fixture</title><body>Visible<script>void "LEAK_SENTINEL"</script><style>.LEAK_SENTINEL{color:red}</style></body>')
    check('inline_module_execution','window.moduleAnswer===42',True,
      '<title>Fixture</title><script type="module">window.moduleAnswer=42</script>',settle=10)
    check('module_external_execution','window.moduleAnswer===42',True,
      '<title>Fixture</title><script type="module" src="/app.mjs"></script>',
      [('https://fixture.test/app.mjs','window.moduleAnswer=42','application/javascript')],settle=10)
    check('storage_roundtrip','(() => {localStorage.setItem("s","42");sessionStorage.setItem("s","43");return [localStorage.getItem("s"),sessionStorage.getItem("s")];})()', ['42','43'])
    check('cookie_roundtrip','(() => {document.cookie="fixture=42; Secure; SameSite=Lax";return document.cookie.includes("fixture=42");})()',True)
    check('structured_clone_transfer','(() => {const a=new Uint8Array([4,2]);const b=structuredClone(a,{transfer:[a.buffer]});return [a.byteLength,...b];})()',[0,4,2])
    check('mutation_observer_delivery','window.mutations',1,
      '<title>Fixture</title><body><script>window.mutations=0;new MutationObserver(e=>mutations+=e.length).observe(document.body,{attributes:true});document.body.setAttribute("data-x","1");</script></body>',settle=10)
    check('promise_microtask_order','window.order',['sync','micro','timer'],
      '<title>Fixture</title><script>window.order=["sync"];Promise.resolve().then(()=>order.push("micro"));setTimeout(()=>order.push("timer"),1);</script>',settle=10)
    check('rejected_promise_event','window.rejectionSeen',True,
      '<title>Fixture</title><script>window.rejectionSeen=false;addEventListener("unhandledrejection",e=>{rejectionSeen=true;e.preventDefault()});Promise.reject(new Error("fixture rejection"));</script>',settle=10)
    check('css_hidden_text','document.querySelector("#box").innerText.includes("HIDDEN")',False,
      '<title>Fixture</title><div id="box">Visible<span style="display:none">HIDDEN</span></div>')
    check('navigation_environment_inherited','({cpu:navigator.hardwareConcurrency,ua:navigator.userAgent.includes("Firefox/158.0"),zone:Intl.DateTimeFormat().resolvedOptions().timeZone})',
      {'cpu':12,'ua':True,'zone':'Asia/Shanghai'})
    check('preload_respects_comment_and_raw_script_text','window.runs===1',True,
      '<title>Fixture</title><!-- <script src="/must-not-request-comment.js"></script> -->'
      '<script>window.example="<script src=\'/must-not-request-literal.js\'>";</script>'
      '<script src="/app.js"></script>',
      [('https://fixture.test/app.js','window.runs=(window.runs||0)+1','application/javascript')])
    check('entity_url_whitespace_and_case','window.runs===1',True,
      '<title>Fixture</title><SCRIPT SRC = "/app.js?a=1&#38;b=2"></SCRIPT>',
      [('https://fixture.test/app.js?a=1&b=2','window.runs=(window.runs||0)+1','application/javascript')])
    check('distinct_inline_modules','window.moduleAnswers',[1,2],
      '<title>Fixture</title><script>window.moduleAnswers=[]</script>'
      '<script type="module">moduleAnswers.push(1)</script>'
      '<script type="module">moduleAnswers.push(2)</script>',settle=10)
    check('inline_module_import_and_scope','window.moduleState',
      {'answer':42,'currentScript':True,'strictThis':True,'scoped':True,'ready':'interactive'},
      '<title>Fixture</title><script type="module">import {answer} from "./app.mjs";'
      'var privateModuleValue=1;window.moduleState={answer,currentScript:document.currentScript===null,'
      'strictThis:this===undefined,scoped:!("privateModuleValue" in window),ready:document.readyState};</script>',
      [('https://fixture.test/app.mjs','export const answer=42','application/javascript')],settle=10)
    check('rejection_event_payload','window.rejectionState',
      {'samePromise':True,'sameReason':True,'trusted':True,'cancelable':True,'target':True},
      '<title>Fixture</title><script>window.rejectionState=null;const why={fixture:42};'
      'const pending=Promise.reject(why);addEventListener("unhandledrejection",e=>{'
      'rejectionState={samePromise:e.promise===pending,sameReason:e.reason===why,'
      'trusted:e.isTrusted,cancelable:e.cancelable,target:e.target===window};e.preventDefault()});</script>',settle=10)
    check('microtask_handled_rejection','window.rejectionCount',0,
      '<title>Fixture</title><script>window.rejectionCount=0;'
      'addEventListener("unhandledrejection",e=>{rejectionCount++;e.preventDefault()});'
      'const pending=Promise.reject("fixture");queueMicrotask(()=>pending.catch(()=>{}));</script>',settle=10)
    check('inner_text_whitespace_and_blocks','document.querySelector("#box").innerText',
      'Alpha beta\nGamma\n\nDelta',
      '<title>Fixture</title><div id="box">  Alpha \n beta  <div>Gamma</div><p>Delta</p></div>')
    check('inner_text_hidden_root_and_detached','(() => {const hidden=document.querySelector("#box");'
      'const detached=document.createElement("div");detached.innerHTML="A<span hidden>B</span>";'
      'return [hidden.innerText,detached.innerText];})()', ['VisibleHIDDEN','AB'],
      '<title>Fixture</title><div id="box" style="display:none">Visible<span>HIDDEN</span></div>')
    check('inner_text_visibility_override','document.querySelector("#box").innerText','Shown',
      '<title>Fixture</title><div id="box"><span style="visibility:hidden">Hidden'
      '<b style="visibility:visible">Shown</b></span></div>')
    check('inner_text_preserves_preformatted','document.querySelector("#box").innerText','  A\n B  ',
      '<title>Fixture</title><div id="box" style="white-space:pre">  A\n B  </div>')
    return cases

CONFIG = {'navigator': {'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:158.0) Gecko/20100101 Firefox/158.0', 'appVersion': '5.0 (Windows)', 'platform': 'Win32', 'language': 'en-US', 'languages': ['en-US', 'en'], 'hardwareConcurrency': 12, 'maxTouchPoints': 0}, 'screen': {'width': 1366, 'height': 768, 'availWidth': 1366, 'availHeight': 720, 'availLeft': 0, 'availTop': 0, 'colorDepth': 24, 'pixelDepth': 24}, 'viewport': {'width': 1360, 'height': 876, 'devicePixelRatio': 1}, 'locale': {'timezone': 'Asia/Shanghai', 'osLocale': 'en-US'}}

def main():
    checks = {}
    for name, script, expected, html, resources, settle in runtime_cases():
        try:
            with Context(timeout=30, proxy='http://127.0.0.1:9', tls='158', environment=CONFIG) as ctx:
                ctx.configure_clock('logical', epoch_ms=1794470400000)
                for url, body, content_type in resources or []:
                    ctx.put_resource(url, body, headers=[['Content-Type', content_type]])
                ctx.load_page('https://fixture.test/', html)
                if settle: ctx.advance(settle, max_tasks=1000)
                actual = ctx.eval(script)
                try:
                    json.dumps(actual, allow_nan=False)
                except (TypeError, ValueError) as exc:
                    raise ValueError(f'Non-JSON fixture result {actual!r}: {exc}') from exc
                network = ctx.net_log()
                matched = all(e.get('matched') and e.get('status') == 200 for e in network)
                checks[name] = dict(passed=actual == expected and matched, actual=actual, expected=expected, network=network)
        except Exception as exc:
            checks[name] = dict(passed=False, error=str(exc))
        print(name, json.dumps(checks[name], ensure_ascii=True), flush=True)
    try:
        with Context(timeout=60, mode='debug') as ctx:
            ctx.eval('const cachedNavigator = navigator')
            ctx.clear_api_log()
            ctx.eval('for(let i=0;i<21000;i++) void cachedNavigator.language')
            stats = ctx.api_log_stats()
            rows = []
            for offset in range(0, stats['entries'], 1000): rows.extend(ctx.peek_api_log_page(offset, 1000))
            checks['api_single_path_pagination'] = dict(passed=len(rows) == 21000 and stats['dropped'] == 0 and
                stats == ctx.api_log_stats() and all(b['n'] == a['n'] + 1 for a, b in zip(rows, rows[1:])),
                stats=stats, received=len(rows))
            checks['api_filtered_page_boundary'] = dict(passed=bool(rows) and
                ctx.peek_api_log_page(20999, 2, filter=rows[0]['p']) == rows[-1:] and
                ctx.peek_api_log_page(21000, 1) == [])
            rejected = []
            for offset, limit in [(-1, 1), (0.5, 1), (1000001, 1), (0, 0), (0, 2001)]:
                try: ctx.peek_api_log_page(offset, limit)
                except Exception: rejected.append((offset, limit))
            checks['api_invalid_pages_preserve_buffer'] = dict(passed=len(rejected) == 5 and
                stats == ctx.api_log_stats(), rejected=rejected)
            ctx.clear_api_log()
            ctx.eval('for(let i=0;i<1000007;i++) void cachedNavigator.language')
            capped = ctx.api_log_stats()
            tail = ctx.peek_api_log_page(999999, 2)
            ctx.eval('void cachedNavigator.language')
            later = ctx.api_log_stats()
            checks['api_capacity_and_exact_drop_count'] = dict(passed=capped ==
                dict(entries=1000000, capacity=1000000, dropped=7) and len(tail) == 1 and
                later == dict(entries=1000000, capacity=1000000, dropped=8), stats=capped, later=later)
            ctx.clear_api_log()
            ctx.eval('void cachedNavigator.language')
            cleared = ctx.api_log_stats()
            checks['api_clear_resets_loss_counter'] = dict(passed=cleared ==
                dict(entries=1, capacity=1000000, dropped=0), stats=cleared)
    except Exception as exc:
        checks['api_pagination_execution'] = dict(passed=False, error=str(exc))
    report = dict(passed=all(v['passed'] for v in checks.values()), checks=checks, python=sys.executable)
    target = Path(__file__).resolve().parents[1] / 'artifacts/browser-compatibility.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(report, indent=2), encoding='utf-8')
    return 0 if report['passed'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
