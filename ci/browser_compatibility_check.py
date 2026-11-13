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
    # Expected CSSOM values are checked against the isolated Firefox control;
    # all image resources are data URLs and need no external transport.
    image = 'data:image/gif;base64,R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=='
    image_url = 'url("' + image + '")'
    setup = 'const e=document.createElement("div");document.body.append(e);const s=e.style;'
    def background(name, body, expected, html='<title>Fixture</title>'):
        check('background_' + name, '(()=>{' + setup + body + '})()', expected, html)
    background('data_uri_shorthand', 's.background=' + json.dumps('url(' + image + ') center / cover') + ';'
        'const c=getComputedStyle(e);return [s.backgroundImage,c.backgroundImage,s.backgroundSize,c.backgroundPosition];',
        [image_url,image_url,'cover','50% 50%'])
    background('resets_longhands',
        's.cssText="background-color:red;background-image:linear-gradient(red,blue);background-position:bottom right;'
        'background-size:12px 13px;background-repeat:no-repeat;background-attachment:fixed;'
        'background-origin:content-box;background-clip:padding-box";s.background="none";'
        'const c=getComputedStyle(e);return [c.backgroundImage,c.backgroundColor,c.backgroundPosition,'
        'c.backgroundSize,c.backgroundRepeat,c.backgroundAttachment,c.backgroundOrigin,c.backgroundClip];',
        ['none','rgba(0, 0, 0, 0)','0% 0%','auto','repeat','scroll','padding-box','border-box'])
    background('declaration_order',
        's.cssText="background:red;background-color:blue";const a=getComputedStyle(e).backgroundColor;'
        's.cssText="background-color:blue;background:red";return [a,getComputedStyle(e).backgroundColor];',
        ['rgb(0, 0, 255)','rgb(255, 0, 0)'])
    background('important_cascade',
        's.cssText="background:red!important;background-color:blue";const a=getComputedStyle(e).backgroundColor;'
        's.cssText="background-color:blue!important;background:red";const b=getComputedStyle(e).backgroundColor;'
        's.setProperty("background","green");return [a,b,getComputedStyle(e).backgroundColor,'
        's.getPropertyPriority("background-color")];',
        ['rgb(255, 0, 0)','rgb(0, 0, 255)','rgb(0, 128, 0)',''])
    background('stylesheet_cascade',
        'e.className="bg";s.backgroundColor="blue";const c=getComputedStyle(e);'
        'return [c.backgroundImage,c.backgroundColor,c.backgroundSize];',
        [image_url,'rgb(255, 0, 0)','cover'],
        '<title>Fixture</title><style>.bg{background:url(' + image + ') center/cover red!important}</style>')
    background('multilayer_and_commas',
        's.background=' + json.dumps('url(' + image + ') left top / 10px 20px no-repeat padding-box content-box, '
        'linear-gradient(red, blue) right bottom / contain fixed #010203') + ';'
        'const c=getComputedStyle(e);return [s.backgroundImage,c.backgroundImage,c.backgroundSize,'
        'c.backgroundPosition,c.backgroundRepeat,c.backgroundAttachment,c.backgroundOrigin,c.backgroundClip,c.backgroundColor];',
        [image_url + ', linear-gradient(red, blue)', image_url + ', linear-gradient(rgb(255, 0, 0), rgb(0, 0, 255))',
         '10px 20px, contain','0% 0%, 100% 100%','no-repeat, repeat','scroll, fixed',
         'padding-box, padding-box','content-box, border-box','rgb(1, 2, 3)'])
    background('remove_and_roundtrip',
        's.background=' + json.dumps('url(' + image + ') center/cover no-repeat red') + ';'
        'const other=document.createElement("div");document.body.append(other);other.style.cssText=s.cssText;'
        'const c=getComputedStyle(other);const before=[c.backgroundImage,c.backgroundSize,c.backgroundColor];'
        'const old=s.removeProperty("background");return {before,returned:old.length>0,empty:s.cssText==="",'
        'longhandsEmpty:["image","size","color","repeat"].every(p=>s.getPropertyValue("background-"+p)==="")};',
        {'before':[image_url,'cover','rgb(255, 0, 0)'],'returned':True,'empty':True,'longhandsEmpty':True})
    background('invalid_preserves_value',
        's.background="blue";const original=s.cssText;'
        'return ["left right","red blue","url(a) url(b)","center / -1px","center / cover contain",'
        '"red, none","none,","/ cover","repeat-x no-repeat","left top right",'
        '"center red top","center no-repeat / cover"].map(v=>{s.background=v;return s.cssText===original});',
        [True]*12)
    background('variables_and_order',
        's.cssText="--bg:red;background:var(--bg);background-color:blue";const a=getComputedStyle(e).backgroundColor;'
        's.cssText="--bg:red;background-color:blue;background:var(--bg)";const b=getComputedStyle(e).backgroundColor;'
        's.cssText="--bg:red;background:var(--bg)!important;background-color:blue";const c=getComputedStyle(e).backgroundColor;'
        's.cssText="background:var(--missing,green)";const d=getComputedStyle(e).backgroundColor;'
        's.cssText="background:var(--missing);background-color:blue";return [a,b,c,d,getComputedStyle(e).backgroundColor];',
        ['rgb(0, 0, 255)','rgb(255, 0, 0)','rgb(255, 0, 0)','rgb(0, 128, 0)','rgb(0, 0, 255)'])
    background('position_and_size',
        'return ["center", "top", "right bottom", "top left", "right 12px bottom 8px",'
        '"bottom 8px right 12px", "center top 8px", "10% 20% / 30px auto"].map(v=>{'
        's.background="none "+v;const c=getComputedStyle(e);return [s.backgroundPosition,c.backgroundPosition,s.backgroundSize]});',
        [['center center','50% 50%','auto'],['center top','50% 0%','auto'],
         ['right bottom','100% 100%','auto'],['left top','0% 0%','auto'],
         ['right 12px bottom 8px','calc(100% - 12px) calc(100% - 8px)','auto'],
         ['right 12px bottom 8px','calc(100% - 12px) calc(100% - 8px)','auto'],
         ['center top 8px','50% 8px','auto'],['10% 20%','10% 20%','30px auto']])
    background('position_longhand_override',
        's.background="none center / cover";s.backgroundPosition="right bottom";'
        'const a=getComputedStyle(e).backgroundPosition;s.backgroundPositionX="10px";'
        'return [a,getComputedStyle(e).backgroundPosition,s.backgroundPosition,s.backgroundSize];',
        ['100% 100%','10px 100%','10px bottom','cover'])
    background('comments_and_keyword_case',
        's.background="NONE /**/ CENTER /**/ / /**/ COVER /**/ NO-REPEAT /**/ RED";'
        'const c=getComputedStyle(e);return [c.backgroundImage,c.backgroundPosition,c.backgroundSize,c.backgroundRepeat,c.backgroundColor];',
        ['none','50% 50%','cover','no-repeat','rgb(255, 0, 0)'])
    background('wide_keywords',
        'document.body.style.background="red center/cover no-repeat";'
        'return ["inherit","initial","unset"].map(v=>{s.background=v;const c=getComputedStyle(e);'
        'return [c.backgroundColor,c.backgroundPosition,c.backgroundSize,c.backgroundRepeat]});',
        [['rgb(255, 0, 0)','50% 50%','cover','no-repeat'],
         ['rgba(0, 0, 0, 0)','0% 0%','auto','repeat'],
         ['rgba(0, 0, 0, 0)','0% 0%','auto','repeat']])
    background('supports_grammars',
        'return {valid:["none","url(data:image/gif;base64,AA==) center/cover","linear-gradient(red,blue) no-repeat",'
        '"left 10px top 20px / 3px 4px red","var(--bg)"].map(v=>CSS.supports("background",v)),'
        'invalid:["bogus","red, none","center / -1px","none,","left right"].map(v=>CSS.supports("background",v)),'
        'images:["none","url(data:image/gif;base64,AA==)","linear-gradient(red,blue)",'
        '"none, url(a)","nonsense", "url(a) url(b)","url(a),"].map(v=>CSS.supports("background-image",v))};',
        {'valid':[True]*5,'invalid':[False]*5,'images':[True]*4+[False]*3})
    background('size_defaults_and_comments',
        'return ["center/30px","center/30px auto","center/auto auto","center/auto 30px",'
        '"center/0","none/**/center"].map(v=>{s.background=v;const c=getComputedStyle(e);'
        'return [s.backgroundPosition,s.backgroundSize,c.backgroundSize]});',
        [['center center','30px auto','30px auto'],['center center','30px auto','30px auto'],
         ['center center','auto','auto'],['center center','auto 30px','auto 30px'],
         ['center center','0px auto','0px auto'],['center center','auto','auto']])
    background('supports_invalid_images',
        'return ["linear-gradient()","url(a b)","image(x)","cross-fade(url(a),url(b),50%)",'
        '"element(#a)","-moz-element(#a)","linear-gradient(red)","image-set(url(a) 1x)",'
        '"top 10px","10px left","center left 10px"].map(v=>CSS.supports("background",v));',
        [False,False,False,False,False,True,True,True,False,False,True])
    background('variable_priority_in_both_orders',
        'return ["--bg:red;background:var(--bg)!important;background-color:blue",'
        '"--bg:red;background-color:blue!important;background:var(--bg)",'
        '"--bg:red;background:var(--bg);background-color:blue!important"].map(v=>{'
        's.cssText=v;return getComputedStyle(e).backgroundColor});',
        ['rgb(255, 0, 0)','rgb(0, 0, 255)','rgb(0, 0, 255)'])
    background('variable_selector_specificity',
        'e.id="bg";e.className="later";const a=getComputedStyle(e).backgroundColor;'
        's.backgroundColor="green";return [a,getComputedStyle(e).backgroundColor];',
        ['rgb(255, 0, 0)','rgb(0, 128, 0)'],
        '<title>Fixture</title><style>body{--bg:red}#bg{background:var(--bg)}.later{background-color:blue}</style>')
    background('variable_specified_getters',
        'return ["--bg:red;background:var(--bg)!important;background-color:blue",'
        '"--bg:red;background:var(--bg);background-color:blue",'
        '"--bg:red;background-color:blue;background:var(--bg)",'
        '"--bg:red;background:var(--bg)!important;background:blue"].map(v=>{'
        's.cssText=v;return [s.background,s.backgroundColor,getComputedStyle(e).backgroundColor]});',
        [['var(--bg)','','rgb(255, 0, 0)'],['','blue','rgb(0, 0, 255)'],
         ['var(--bg)','','rgb(255, 0, 0)'],['var(--bg)','','rgb(255, 0, 0)']])
    background('omitted_color_default',
        's.background="none";return [s.backgroundColor,getComputedStyle(e).backgroundColor];',
        ['rgba(0, 0, 0, 0)','rgba(0, 0, 0, 0)'])
    background('relative_lengths',
        's.fontSize="20px";s.background="right 2em bottom 1em / 3em auto";'
        'const c=getComputedStyle(e);return [s.backgroundPosition,c.backgroundPosition,c.backgroundSize];',
        ['right 2em bottom 1em','calc(100% - 40px) calc(100% - 20px)','60px auto'])
    background('gradient_default_positions',
        's.background="radial-gradient(circle at center,red,blue),conic-gradient(from 90deg at center,red,blue)";'
        'return [s.backgroundImage,getComputedStyle(e).backgroundImage];',
        ['radial-gradient(circle, red, blue), conic-gradient(from 90deg, red, blue)',
         'radial-gradient(circle, rgb(255, 0, 0), rgb(0, 0, 255)), conic-gradient(from 90deg, rgb(255, 0, 0), rgb(0, 0, 255))'])
    background('image_set_computed_density',
        's.backgroundImage=' + json.dumps('image-set(' + image_url + ' 1x)') + ';'
        'return [s.backgroundImage,getComputedStyle(e).backgroundImage];',
        ['image-set(' + image_url + ' 1x)','image-set(' + image_url + ' 1dppx)'])
    density_url = 'url("data:image/gif;base64,AA==")'
    density_units = ['1x', '2dppx', '96dpi', '2dpcm', '0x', '-1x', '1px', '2dppx 3x', '']
    density_expected = []
    for unit, computed in [('1x','1dppx'),('2dppx','2dppx'),('96dpi','1dppx'),
                           ('2dpcm','0.0529167dppx'),('0x','0dppx'),('-1x',None),
                           ('1px',None),('2dppx 3x',None),('','1dppx')]:
        density_expected.append([computed is not None,
            'image-set(' + density_url + ' ' + (unit or '1x') + ')' if computed is not None else '',
            'image-set(' + density_url + ' ' + computed + ')' if computed is not None else 'none'])
    background('image_set_resolution_units',
        'return ' + json.dumps(density_units) + '.map(unit=>{'
        'const value="image-set(url(data:image/gif;base64,AA==)"+(unit?" "+unit:"")+")";'
        's.cssText="";s.backgroundImage=value;return [CSS.supports("background-image",value),'
        's.backgroundImage,getComputedStyle(e).backgroundImage]});', density_expected)
    background('explicit_transparent_preserved',
        's.background="transparent";return [s.backgroundColor,getComputedStyle(e).backgroundColor];',
        ['transparent','rgba(0, 0, 0, 0)'])
    background('empty_image_url',
        'return ["url()",\'url("")\'].map(value=>{s.background=value;'
        'return [s.backgroundImage,getComputedStyle(e).backgroundImage]});',
        [['url("")','url("")'],['url("")','url("")']])
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"><rect width="1" height="1"/></svg>'
    check('background_relative_inline_url',
        '(()=>{const e=document.querySelector("#bg");return [e.style.backgroundImage,getComputedStyle(e).backgroundImage]})()',
        ['url("./images/pixel.svg")','url("https://fixture.test/images/pixel.svg")'],
        '<title>Fixture</title><div id="bg" style="background:url(./images/pixel.svg)"></div>',
        [('https://fixture.test/images/pixel.svg',svg,'image/svg+xml')])
    check('background_external_sheet_url_base',
        'getComputedStyle(document.querySelector("#bg")).backgroundImage',
        'url("https://fixture.test/assets/images/pixel.svg")',
        '<title>Fixture</title><link rel="stylesheet" href="/assets/css/app.css"><div id="bg"></div>',
        [('https://fixture.test/assets/css/app.css','#bg{background:url(../images/pixel.svg)}','text/css'),
         ('https://fixture.test/assets/images/pixel.svg',svg,'image/svg+xml')])
    check('background_document_base_url',
        'getComputedStyle(document.querySelector("#bg")).backgroundImage',
        'url("https://fixture.test/assets/images/pixel.svg")',
        '<title>Fixture</title><base href="https://fixture.test/assets/"><style>#bg{background:url(images/pixel.svg)}</style><div id="bg"></div>',
        [('https://fixture.test/assets/images/pixel.svg',svg,'image/svg+xml')])
    return cases

PROFILE_EXTENSION_NAMES = ['ANGLE_instanced_arrays', 'EXT_blend_minmax', 'EXT_color_buffer_half_float', 'EXT_depth_clamp', 'EXT_disjoint_timer_query', 'EXT_float_blend', 'EXT_frag_depth', 'EXT_sRGB', 'EXT_shader_texture_lod', 'EXT_texture_compression_bptc', 'EXT_texture_compression_rgtc', 'EXT_texture_filter_anisotropic', 'EXT_texture_norm16', 'OES_draw_buffers_indexed', 'OES_element_index_uint', 'OES_fbo_render_mipmap', 'OES_standard_derivatives', 'OES_texture_float', 'OES_texture_float_linear', 'OES_texture_half_float', 'OES_texture_half_float_linear', 'OES_vertex_array_object', 'WEBGL_color_buffer_float', 'WEBGL_compressed_texture_astc', 'WEBGL_compressed_texture_etc', 'WEBGL_compressed_texture_etc1', 'WEBGL_compressed_texture_pvrtc', 'WEBGL_compressed_texture_s3tc', 'WEBGL_compressed_texture_s3tc_srgb', 'WEBGL_debug_renderer_info', 'WEBGL_debug_shaders', 'WEBGL_depth_texture', 'WEBGL_draw_buffers', 'WEBGL_explicit_present', 'WEBGL_lose_context']

def device_memory_checks(Context):
    checks = {}
    def record(name, actual, expected):
        checks[name] = dict(passed=actual == expected, actual=actual, expected=expected)
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        ctx.load_page('https://fixture.test/', '')
        record('memory_default_absent', ctx.eval(
            '({present:"deviceMemory" in navigator,own:Object.hasOwn(Navigator.prototype,"deviceMemory")})'),
            dict(present=False, own=False))
    with Context(timeout=30, mode='debug', proxy='http://127.0.0.1:9') as ctx:
        configured = ctx.configure_environment({'navigator':{'deviceMemory':16}})
        record('memory_configuration_reflected', configured['navigator']['deviceMemory'], 16)
        ctx.load_page('https://fixture.test/', '<iframe></iframe>')
        record('memory_native_descriptor', ctx.eval("""(() => {
            const d=Object.getOwnPropertyDescriptor(Navigator.prototype,'deviceMemory');
            let invalid=false;try{d.get.call({});}catch(e){invalid=e instanceof TypeError;}
            return {value:navigator.deviceMemory,type:typeof navigator.deviceMemory,
                own:Object.hasOwn(navigator,'deviceMemory'),getter:typeof d.get,
                setter:typeof d.set,enumerable:d.enumerable,configurable:d.configurable,
                native:Function.prototype.toString.call(d.get).includes('[native code]'),invalid};
        })()"""), dict(value=16,type='number',own=False,getter='function',setter='undefined',
                     enumerable=True,configurable=True,native=True,invalid=True))
        record('memory_frame_inheritance', ctx.eval(
            'document.querySelector("iframe").contentWindow.navigator.deviceMemory'),16)
        ctx.eval("""window.memoryWorker=null;
            const u=URL.createObjectURL(new Blob([
              'const d=Object.getOwnPropertyDescriptor(WorkerNavigator.prototype,"deviceMemory");'
              +'let invalid=false;try{d.get.call({});}catch(e){invalid=e instanceof TypeError;}'
              +'postMessage({value:navigator.deviceMemory,native:d.get.toString().includes("[native code]"),invalid});'
            ],{type:'application/javascript'}));
            const w=new Worker(u);w.onmessage=e=>{memoryWorker=e.data;w.terminate();URL.revokeObjectURL(u);};void 0;""")
        for _ in range(50):
            ctx.advance(20,max_tasks=2000)
            worker=ctx.eval('window.memoryWorker')
            if worker is not None: break
        record('memory_worker_inheritance',worker,dict(value=16,native=True,invalid=True))
        record('memory_api_observed', any(x.get('p')=='Navigator.deviceMemory'
            for x in ctx.peek_api_log()),True)
        ctx.put_resource('https://next.fixture.test/', '<title>successor</title>',
            headers=[['Content-Type','text/html']])
        ctx.navigate('https://next.fixture.test/')
        record('memory_navigation_inheritance',ctx.eval('navigator.deviceMemory'),16)
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        ctx.configure_environment({'navigator':{'deviceMemory':0.5}})
        record('memory_fractional_gib',ctx.eval('navigator.deviceMemory'),0.5)
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        ctx.configure_environment({'navigator':{'deviceMemory':16}})
        rejected=[]
        for value in [0,-1,129,'16',False]:
            try: ctx.configure_environment({'navigator':{'deviceMemory':value}})
            except Exception: rejected.append(value)
        state=ctx.configure_environment({'navigator':{'language':'zh-CN'}})
        record('memory_invalid_configuration_atomic',
            dict(rejected=len(rejected),value=state['navigator']['deviceMemory']),
            dict(rejected=5,value=16))
        ctx.configure_environment({'navigator':{'deviceMemory':None}})
        record('memory_explicit_disable',ctx.eval('"deviceMemory" in navigator'),False)
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        ctx.configure_environment({'navigator':{'deviceMemory':16}})
        ctx.load_page('http://insecure.fixture.test/','')
        record('memory_secure_context_gate',ctx.eval(
            '({secure:isSecureContext,present:"deviceMemory" in navigator})'),
            dict(secure=False,present=False))
        ctx.load_page('https://fixture.test/','')
        record('memory_secure_context_reenabled',ctx.eval('navigator.deviceMemory'),16)
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        ctx.configure_environment({'webgl':{'extensions':PROFILE_EXTENSION_NAMES}})
        actual=ctx.eval("""(() => { const g=document.createElement('canvas').getContext('webgl');
          const names=g.getSupportedExtensions();
          return {names,available:names.every(name=>g.getExtension(name)!==null)};})()""")
        record('webgl_35_extensions_roundtrip',actual,
            dict(names=PROFILE_EXTENSION_NAMES,available=True))
    with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
        rejected=[]
        for group in [{'webgl':{'extensions':['EXT_clip_control']*129}},
                      {'navigator':{'languages':['en-US']*33}}]:
            try:ctx.configure_environment(group)
            except Exception:rejected.append(True)
        record('webgl_and_language_list_bounds',len(rejected),2)
    checks.update(graphics_profile_checks(Context))
    return checks

def graphics_profile_checks(Context):
    import json
    checks = {}
    def record(name, actual, expected):
        checks[name] = dict(passed=actual == expected, actual=actual, expected=expected)
    read = """(() => {
        const canvas=typeof document==='object'?document.createElement('canvas'):new OffscreenCanvas(4,4);
        const g=canvas.getContext('webgl'),d=g.getExtension('WEBGL_debug_renderer_info');
        return {vendor:g.getParameter(g.VENDOR),renderer:g.getParameter(d.UNMASKED_RENDERER_WEBGL),
            limit:g.getParameter(g.MAX_VERTEX_UNIFORM_VECTORS),extensions:g.getSupportedExtensions()};
    })()"""
    expected=dict(vendor='WebKit',renderer='YSbrowser measured Intel fixture',limit=4096,
        extensions=['EXT_clip_control','WEBGL_debug_renderer_info'])
    with Context(timeout=30,proxy='http://127.0.0.1:9') as ctx:
        ctx.configure_environment({'webgl':{'vendor':expected['vendor'],
            'unmaskedRenderer':expected['renderer'],'limits':{'36347':expected['limit']},
            'extensions':expected['extensions']}})
        ctx.put_resource('https://child.fixture.test/','<iframe></iframe>',
            headers=[['Content-Type','text/html']])
        ctx.load_page('https://fixture.test/','<iframe></iframe><iframe src="https://child.fixture.test/"></iframe>')
        record('webgl_page_profile',ctx.eval(read),expected)
        for index,label in [(0,'blank_frame'),(1,'cross_origin_frame')]:
            frame='document.querySelectorAll("iframe")['+str(index)+'].contentWindow'
            record('webgl_'+label+'_profile',ctx.eval(frame+'.eval('+json.dumps(read)+')'),expected)
        nested='document.querySelectorAll("iframe")[1].contentWindow.document.querySelector("iframe").contentWindow'
        record('webgl_nested_frame_profile',ctx.eval(nested+'.eval('+json.dumps(read)+')'),expected)
        worker_source='postMessage('+read+');'
        setup="""window.workerGraphics=null;
            const u=URL.createObjectURL(new Blob([CODE],{type:'application/javascript'}));
            const w=new Worker(u);w.onmessage=e=>{workerGraphics=e.data;w.terminate();URL.revokeObjectURL(u);};void 0;
        """.replace('CODE',json.dumps(worker_source))
        frame='document.querySelectorAll("iframe")[1].contentWindow'
        ctx.eval(frame+'.eval('+json.dumps(setup)+')')
        for _ in range(50):
            ctx.advance(20,max_tasks=2000)
            worker=ctx.eval(frame+'.workerGraphics')
            if worker is not None:break
        record('webgl_worker_from_frame_profile',worker,expected)
        ctx.put_resource('https://next.fixture.test/','<iframe></iframe>',
            headers=[['Content-Type','text/html']])
        ctx.navigate('https://next.fixture.test/')
        record('webgl_successor_frame_profile',ctx.eval(
            'document.querySelector("iframe").contentWindow.eval('+json.dumps(read)+')'),expected)
    return checks


"""Local resource checks for the native changes selected from memory evidence."""
import json


def memory_environment_checks(Context, snapshot=None):
    checks = {}
    def record(name, actual, expected):
        checks[name] = {'passed':actual == expected, 'actual':actual, 'expected':expected}
    if snapshot:
        try:
            with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
                ctx.load_page('https://fixture.test/', '<title>Fixture</title>')
                state = ctx.eval(snapshot)
                json.dumps(state, allow_nan=False)
                record('snapshot_missing_api_serializable',state['navigator']['deviceMemory'],{'unavailable':True})
        except Exception as exc:
            checks['snapshot_missing_api_serializable'] = {'passed':False, 'error':str(exc)}
    read = '''({navigator:'gpu' in navigator,constructor:typeof GPU,
        globals:Object.getOwnPropertyNames(globalThis).filter(k=>k.startsWith('GPU')||k==='WGSLLanguageFeatures').length})'''
    absent = {'navigator':False, 'constructor':'undefined', 'globals':0}
    try:
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'webgpu':{'exposed':False}})
            rejected = 0
            for invalid in [None, 0, 'false', []]:
                try:
                    ctx.configure_environment({'webgpu':{'exposed':invalid}})
                except Exception:
                    rejected += 1
            state = ctx.configure_environment({'navigator':{'maxTouchPoints':5}})
            record('gpu_exposure_configuration_atomic',
                {'rejected':rejected, 'exposed':state['webgpu']['exposed']},
                {'rejected':4, 'exposed':False})
            ctx.put_resource('https://child.fixture.test/', '<iframe></iframe>',
                headers=[['Content-Type','text/html']])
            ctx.load_page('https://fixture.test/', '<iframe></iframe><iframe src="https://child.fixture.test/"></iframe>')
            record('gpu_hidden_page', ctx.eval(read), absent)
            for i in range(2):
                frame = 'document.querySelectorAll("iframe")[' + str(i) + '].contentWindow'
                record('gpu_hidden_frame_' + str(i), ctx.eval(frame+'.eval('+json.dumps(read)+')'), absent)
            frame = 'document.querySelectorAll("iframe")[1].contentWindow'
            setup = '''window.workerGpu=null;
                const u=URL.createObjectURL(new Blob([CODE],{type:'application/javascript'}));
                const w=new Worker(u);w.onmessage=e=>{workerGpu=e.data;w.terminate();URL.revokeObjectURL(u)};void 0;'''
            setup = setup.replace('CODE', json.dumps('postMessage('+read+')'))
            ctx.eval(frame+'.eval('+json.dumps(setup)+')')
            value = None
            for _ in range(50):
                ctx.advance(20, max_tasks=2000)
                value = ctx.eval(frame+'.workerGpu')
                if value is not None:
                    break
            record('gpu_hidden_worker_from_frame', value, absent)
            ctx.load_page('http://insecure.fixture.test/', '')
            record('gpu_hidden_insecure_document', ctx.eval(read), absent)
            ctx.load_page('https://next.fixture.test/', '')
            record('gpu_hidden_successor_document', ctx.eval(read), absent)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'webgpu':{'exposed':False}})
            ctx.configure_environment({'webgpu':{'exposed':True}})
            ctx.load_page('https://fixture.test/', '')
            record('gpu_exposure_reenabled', ctx.eval("'gpu' in navigator && typeof GPU==='function'"), True)
            ctx.eval('window.adapterDone=false;window.noAdapter=false;navigator.gpu.requestAdapter().then(a=>{noAdapter=a===null;adapterDone=true});void 0;')
            ctx.advance(10, max_tasks=1000)
            record('gpu_exposure_does_not_enable_adapter', ctx.eval('adapterDone && noAdapter'), True)
    except Exception as exc:
        checks['gpu_exposure_execution'] = {'passed':False, 'error':str(exc)}

    # A new contact must activate the actual target, use that target's realm and
    # retain TouchList invariants. The page's constructor cannot create it.
    try:
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'navigator':{'maxTouchPoints':0},
                'input':{'touchEvents':'enabled'}})
            rejected = 0
            for invalid in [None, True, 1, 'unknown']:
                try:
                    ctx.configure_environment({'input':{'touchEvents':invalid}})
                except Exception:
                    rejected += 1
            state = ctx.configure_environment({'navigator':{'language':'zh-CN'}})
            record('touch_exposure_invalid_configuration_atomic',
                {'rejected':rejected, 'policy':state['input']['touchEvents']},
                {'rejected':4, 'policy':'enabled'})
            record('touch_exposure_independent_of_point_count', ctx.eval(
                'navigator.maxTouchPoints===0 && typeof TouchEvent==="function"'), True)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'input':{'touchEvents':'enabled'}})
            ctx.configure_environment({'input':{'touchEvents':'disabled'}})
            record('touch_exposure_explicit_disable', ctx.eval('typeof TouchEvent'), 'undefined')
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'input':{'touchEvents':'disabled'}})
            ctx.configure_environment({'input':{'touchEvents':'enabled'}})
            ctx.load_page('https://fixture.test/', '<iframe></iframe>')
            record('touch_exposure_frame_inheritance', ctx.eval(
                'typeof document.querySelector("iframe").contentWindow.TouchEvent'), 'function')
    except Exception as exc:
        checks['touch_exposure_execution'] = {'passed':False, 'error':str(exc)}

    html = '''<style>button{margin:30px;width:80px;height:40px}</style>
        <button id="target">Tap</button><script>
        window.events=[];window.activations=0;window.cancelTouch=false;
        const target=document.getElementById('target');
        target.addEventListener('click',()=>activations++);
        for(const type of ['pointerdown','pointerup','touchstart','touchend','click'])
          target.addEventListener(type,e=>{
            const t=e.changedTouches&&e.changedTouches[0];
            const r=target.getBoundingClientRect();
            events.push({type:e.type,trusted:e.isTrusted,time:e.timeStamp,
              touch:t?{touches:e.touches.length,changed:e.changedTouches.length,
                targetTouches:e.targetTouches.length,target:t.target===target,
                inRealm:e instanceof TouchEvent,inside:t.clientX>=r.left&&t.clientX<=r.right&&t.clientY>=r.top&&t.clientY<=r.bottom}:null,
              pointer:e.pointerType||null});
            if(type==='touchstart'&&cancelTouch)e.preventDefault();
          });
        window.Touch=function(){throw new Error('page constructor must not create host input')};
        </script>'''
    try:
        for frame in (False, True):
            label = 'frame' if frame else 'page'
            with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
                ctx.configure_environment({'navigator':{'maxTouchPoints':5},
                    'input':{'touchEvents':'enabled'}})
                ctx.configure_clock('logical', epoch_ms=1794535200000)
                if frame:
                    ctx.put_resource('https://child.fixture.test/', html,
                        headers=[['Content-Type','text/html']])
                    ctx.load_page('https://fixture.test/', '<iframe src="https://child.fixture.test/"></iframe>')
                    owner = 'document.querySelector("iframe").contentWindow'
                else:
                    ctx.load_page('https://fixture.test/', html)
                    owner = 'window'
                target = owner + '.document.getElementById("target")'
                ctx.tap(target, hold_ms=80)
                events = ctx.eval(owner+'.events')
                contacts = [e for e in events if e['touch']]
                down = next((e for e in events if e['type']=='pointerdown'), {})
                record('tap_'+label+'_activates_target', ctx.eval(owner+'.activations'), 1)
                record('tap_'+label+'_trusted_touch_pointer',
                    bool(events) and all(e['trusted'] for e in events) and down.get('pointer')=='touch', True)
                record('tap_'+label+'_contact_invariants',
                    [(e['type'], e['touch']) for e in contacts], [
                        ('touchstart',dict(touches=1,changed=1,targetTouches=1,target=True,inRealm=True,inside=True)),
                        ('touchend',dict(touches=0,changed=1,targetTouches=0,target=True,inRealm=True,inside=True))])
                record('tap_'+label+'_clock_duration',
                    len(contacts)==2 and contacts[1]['time']-contacts[0]['time']>=80, True)
                ctx.eval(owner+'.cancelTouch=true;'+owner+'.events=[];void 0;')
                ctx.tap(target)
                record('tap_'+label+'_cancellation_suppresses_activation',ctx.eval(owner+'.activations'),1)
                ctx.click(target)
                record('mouse_'+label+'_activation_preserved',ctx.eval(owner+'.activations'),2)
    except Exception as exc:
        checks['touch_input_execution'] = {'passed':False, 'error':str(exc)}
    checks.update(scrollbar_environment_checks(Context))
    checks.update(touch_handler_environment_checks(Context))
    return checks


def scrollbar_environment_checks(Context):
    """Exercise overflow geometry instead of comparing only an empty viewport."""
    checks = {}

    def record(name, actual, expected):
        checks[name] = {'passed': actual == expected, 'actual': actual, 'expected': expected}

    dimensions = '''[innerWidth,innerHeight,document.documentElement.clientWidth,
        document.documentElement.clientHeight,document.documentElement.scrollWidth]'''
    tall = '<!doctype html><style>body{margin:0;height:3000px}</style>'
    try:
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'viewport': {'width': 414, 'height': 774}})
            ctx.load_page('https://fixture.test/', tall)
            record('scrollbar_vertical_overflow_no_spurious_horizontal',
                   ctx.eval(dimensions), [414, 774, 397, 774, 397])
            ctx.eval('document.body.style.height="1px";void 0;')
            record('scrollbar_overflow_removed_invalidates_layout',
                   ctx.eval(dimensions), [414, 774, 414, 774, 414])
            ctx.eval('document.body.style.height="3000px";void 0;')
            record('scrollbar_overflow_added_invalidates_layout',
                   ctx.eval(dimensions), [414, 774, 397, 774, 397])
            ctx.eval('document.documentElement.style.scrollbarWidth="none";void 0;')
            record('scrollbar_root_none_reserves_no_space',
                   ctx.eval(dimensions), [414, 774, 414, 774, 414])
            record('scrollbar_root_none_remains_scrollable', ctx.eval(
                'scrollTo(0,120);scrollY===120 && document.documentElement.scrollHeight===3000'), True)
            ctx.eval('document.documentElement.style.scrollbarWidth="auto";'
                     'document.body.style.scrollbarWidth="none";void 0;')
            record('scrollbar_body_none_does_not_propagate_to_viewport',
                   ctx.eval(dimensions), [414, 774, 397, 774, 397])
            record('scrollbar_fixture_uses_no_external_network',
                   any(not e.get('matched') for e in ctx.net_log()), False)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'viewport': {'width': 414, 'height': 774, 'scrollbarWidth': 0}})
            rejected = 0
            for invalid in [None, True, '0', [], -1, 65, float('nan'), float('inf')]:
                try:
                    ctx.configure_environment({'viewport': {'width': 500, 'scrollbarWidth': invalid}})
                except Exception:
                    rejected += 1
            state = ctx.configure_environment({'navigator': {'language': 'zh-CN'}})
            record('scrollbar_invalid_configuration_is_atomic',
                   [rejected, state['viewport']['width'], state['viewport']['scrollbarWidth']], [8, 414, 0])
            ctx.put_resource('https://child.fixture.test/', tall,
                             headers=[['Content-Type', 'text/html']])
            ctx.load_page('https://fixture.test/', tall +
                '<iframe style="width:320px;height:240px;border:0" src="https://child.fixture.test/"></iframe>')
            record('scrollbar_overlay_root_keeps_viewport',
                   ctx.eval(dimensions), [414, 774, 414, 774, 414])
            record('scrollbar_overlay_inherited_by_frame', ctx.eval(
                'document.querySelector("iframe").contentWindow.eval('+json.dumps(dimensions)+')'),
                [320, 240, 320, 240, 320])
            ctx.load_page('https://next.fixture.test/', tall)
            record('scrollbar_overlay_survives_navigation',
                   ctx.eval(dimensions), [414, 774, 414, 774, 414])
            record('scrollbar_overlay_remains_scrollable', ctx.eval(
                'scrollTo(0,120);scrollY===120 && document.documentElement.scrollHeight===3000'), True)
        scroller = '''<!doctype html><style>body{margin:0}
            #s{width:100px;height:100px;overflow:scroll}
            #s>div{width:300px;height:300px}</style><div id="s"><div></div></div>'''
        for width in (17, 12, 0):
            with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
                ctx.configure_environment({'viewport': {'scrollbarWidth': width}})
                ctx.load_page('https://fixture.test/', scroller)
                read = '(()=>{const s=document.getElementById("s");return [s.clientWidth,s.clientHeight,s.scrollWidth,s.scrollHeight]})()'
                record('scrollbar_nested_width_'+str(width), ctx.eval(read), [100-width, 100-width, 300, 300])
                ctx.eval('document.getElementById("s").style.scrollbarWidth="none";void 0;')
                record('scrollbar_nested_none_'+str(width), ctx.eval(read), [100, 100, 300, 300])
    except Exception as exc:
        checks['scrollbar_layout_execution'] = {'passed': False, 'error': str(exc)}
    return checks


TOUCH_HANDLER_SOURCE = '''(()=>{
  const names=['ontouchstart','ontouchend','ontouchmove','ontouchcancel'];
  const objects=[window,document,document.createElement('div'),
    document.createElementNS('http://www.w3.org/2000/svg','svg'),
    document.createElementNS('http://www.w3.org/1998/Math/MathML','math')];
  let factory;
  try {const e=document.createEvent('TouchEvent');
    factory=[e instanceof TouchEvent,e.type,e.isTrusted,e.touches.length];}
  catch(e){factory=e.name}
  return {handlers:objects.map(o=>names.map(n=>n in o)),
    defaults:objects.map(o=>names.every(n=>o[n]===null)),
    elementPrototypeOwns:Object.hasOwn(Element.prototype,'ontouchstart'),factory};
})()'''


def touch_handler_environment_checks(Context):
    """Exercise feature-gated subscription, IDL setters and actual input delivery."""
    checks = {}

    def record(name, actual, expected):
        checks[name] = {'passed': actual == expected, 'actual': actual, 'expected': expected}

    enabled = dict(handlers=[[True]*4 for _ in range(5)], defaults=[True]*5,
                   elementPrototypeOwns=False, factory=[True, '', False, 0])
    absent = dict(handlers=[[False]*4 for _ in range(5)], defaults=[False]*5,
                  elementPrototypeOwns=False, factory='NotSupportedError')
    html = '''<!doctype html><button id="t" style="width:80px;height:40px"
        ontouchstart="window.attributeSeen++">Tap</button><script>
        window.attributeSeen=0;window.seen=[];window.activations=0;
        const t=document.getElementById('t');
        t.addEventListener('click',()=>activations++);
        if('ontouchstart' in window){
          addEventListener('touchstart',e=>seen.push(['listener',e.isTrusted]));
          document.ontouchend=function(e){seen.push(['document',e.isTrusted,this===document])};
          window.ontouchend=function(e){seen.push(['window',e.isTrusted,this===window])};
        }
        </script>'''
    try:
        for frame in (False, True):
            label = 'frame' if frame else 'page'
            with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
                ctx.configure_environment({'input': {'touchEvents': 'enabled'},
                                           'navigator': {'maxTouchPoints': 0}})
                if frame:
                    ctx.put_resource('https://child.fixture.test/', html,
                                     headers=[['Content-Type', 'text/html']])
                    ctx.load_page('https://fixture.test/', '<iframe src="https://child.fixture.test/"></iframe>')
                    owner = 'document.querySelector("iframe").contentWindow'
                else:
                    ctx.load_page('https://fixture.test/', html)
                    owner = 'window'
                evaluate = lambda code: ctx.eval(owner+'.eval('+json.dumps(code)+')')
                record('touch_handlers_'+label+'_exposure', evaluate(TOUCH_HANDLER_SOURCE), enabled)
                ctx.tap(owner+'.document.getElementById("t")')
                record('touch_handlers_'+label+'_feature_gated_native_delivery', evaluate('seen'),
                       [['listener', True], ['document', True, True], ['window', True, True]])
                record('touch_handlers_'+label+'_content_attribute', evaluate('attributeSeen'), 1)
                record('touch_handlers_'+label+'_activation', evaluate('activations'), 1)
                evaluate('document.getElementById("t").ontouchstart=function(){return false};void 0')
                ctx.tap(owner+'.document.getElementById("t")')
                record('touch_handlers_'+label+'_return_false_cancels_activation', evaluate('activations'), 1)
                record('touch_handlers_'+label+'_setter_normalizes_primitive', evaluate(
                    'document.ontouchend=42;document.ontouchend===null'), True)
                record('touch_handlers_'+label+'_setter_rejects_wrong_receiver', evaluate('''(()=>{
                    const d=Object.getOwnPropertyDescriptor(Document.prototype,'ontouchend');
                    if(!d||typeof d.set!=='function')return false;
                    try{d.set.call({},()=>{});return false}
                    catch(e){return e instanceof TypeError}})()'''), True)
        for policy in ('auto', 'disabled'):
            with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
                ctx.configure_environment({'input': {'touchEvents': 'enabled'}})
                ctx.configure_environment({'input': {'touchEvents': policy}})
                ctx.load_page('https://fixture.test/', '')
                record('touch_handlers_'+policy+'_removes_exposure', ctx.eval(TOUCH_HANDLER_SOURCE), absent)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.configure_environment({'input': {'touchEvents': 'disabled'}})
            ctx.configure_environment({'input': {'touchEvents': 'enabled'}})
            ctx.load_page('https://first.fixture.test/', '')
            ctx.load_page('http://next.fixture.test/', '')
            record('touch_handlers_reenabled_and_navigation_inherited', ctx.eval(TOUCH_HANDLER_SOURCE), enabled)
    except Exception as exc:
        checks['touch_handlers_execution'] = {'passed': False, 'error': str(exc)}
    return checks


MEMORY_SNAPSHOT = '(() => {\n  const read = fn => {\n    try {\n      const value = fn();\n      return value === undefined ? {unavailable: true} : value;\n    } catch (e) { return {error: String(e)}; }\n  };\n  const text = node => {\n    if (!node) return \'\';\n    if (node.nodeType === 3) return node.nodeValue || \'\';\n    if ([\'SCRIPT\',\'STYLE\',\'NOSCRIPT\',\'TEMPLATE\'].includes(node.nodeName)) return \'\';\n    return [...node.childNodes].map(text).join(\' \');\n  };\n  const rect = e => {\n    const r = e.getBoundingClientRect();\n    return {x: r.x, y: r.y, width: r.width, height: r.height};\n  };\n  const graphics = () => {\n    const first = document.createElement(\'canvas\').getContext(\'webgl\');\n    const second = document.createElement(\'canvas\').getContext(\'webgl2\');\n    if (!first || !second) return {error:\'WebGL context unavailable\'};\n    const d = first.getExtension(\'WEBGL_debug_renderer_info\');\n    const attributes = first.getContextAttributes();\n    return {vendor:first.getParameter(first.VENDOR),renderer:first.getParameter(first.RENDERER),\n      version:first.getParameter(first.VERSION),glslVersion:first.getParameter(first.SHADING_LANGUAGE_VERSION),\n      unmaskedVendor:d?first.getParameter(d.UNMASKED_VENDOR_WEBGL):null,\n      unmaskedRenderer:d?first.getParameter(d.UNMASKED_RENDERER_WEBGL):null,\n      version2:second.getParameter(second.VERSION),glslVersion2:second.getParameter(second.SHADING_LANGUAGE_VERSION),\n      attributes:Object.fromEntries([\'alpha\',\'antialias\',\'depth\',\'failIfMajorPerformanceCaveat\',\n        \'powerPreference\',\'premultipliedAlpha\',\'preserveDrawingBuffer\',\'stencil\'].map(k=>[k,attributes[k]])),\n      extensions:first.getSupportedExtensions(),extensions2:second.getSupportedExtensions(),\n      limits:Object.fromEntries([3379,34076,34024,34921,34930,35660,35661,36347,36349,36348]\n        .map(k=>[String(k),first.getParameter(k)]))};\n  };\n  const globals = ["fetch", "XMLHttpRequest", "Worker", "SharedWorker", "MessageChannel",\n    "MessagePort", "MutationObserver", "ResizeObserver", "IntersectionObserver",\n    "OffscreenCanvas", "WebGLRenderingContext", "WebGL2RenderingContext", "AudioContext",\n    "RTCPeerConnection", "crypto", "WebAssembly", "indexedDB", "localStorage",\n    "sessionStorage", "CSS", "matchMedia", "requestAnimationFrame", "structuredClone"];\n  const scrollbarWidth = () => {\n    const probe = document.createElement(\'div\');\n    probe.style.cssText = \'position:absolute;left:-10000px;top:-10000px;width:100px;height:100px;overflow:scroll;border:0;padding:0;visibility:hidden\';\n    (document.body || document.documentElement).appendChild(probe);\n    try { return probe.offsetWidth - probe.clientWidth; }\n    finally { probe.remove(); }\n  };\n  return {\n    url: location.href, title: document.title, readyState: document.readyState,\n    secure: isSecureContext,\n    navigator: Object.fromEntries(["userAgent", "appVersion", "platform", "language",\n      "languages", "hardwareConcurrency", "deviceMemory", "maxTouchPoints", "vendor", "productSub",\n      "webdriver", "cookieEnabled", "onLine", "appCodeName", "appName", "product", "vendorSub",\n      "oscpu", "buildID", "doNotTrack", "pdfViewerEnabled", "globalPrivacyControl"].map(k => [k, read(() => navigator[k])])),\n    screen: Object.fromEntries(["width", "height", "availWidth", "availHeight", "availLeft",\n      "availTop", "colorDepth", "pixelDepth", "top", "left"].map(k => [k, read(() => screen[k])])),\n    viewport: {width: innerWidth, height: innerHeight, devicePixelRatio,\n      scrollbarWidth: read(scrollbarWidth)},\n    documentViewport: {client: read(() => [document.documentElement.clientWidth,\n      document.documentElement.clientHeight]), scroll: read(() => [document.documentElement.scrollWidth,\n      document.documentElement.scrollHeight])},\n    locale: {timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,\n      osLocale: Intl.DateTimeFormat().resolvedOptions().locale},\n    webgl: read(graphics),\n    webgpu: {exposed: read(() => \'gpu\' in navigator)},\n    input: {touchEvents: read(() => typeof TouchEvent === \'function\' ? \'enabled\' : \'disabled\')},\n    capabilities: Object.fromEntries(globals.map(k => [k, read(() => typeof globalThis[k])])),\n    crypto: {subtle: read(() => typeof crypto.subtle),\n      getRandomValues: read(() => typeof crypto.getRandomValues)},\n    application: {jquery: read(() => typeof jQuery === "function" ? jQuery.fn.jquery : null),\n      hcaptcha: read(() => typeof hcaptcha), refreshCaptcha: read(() => typeof RefreshCaptcha),\n      hcaptchaMethods: read(() => typeof hcaptcha === \'object\' ?\n        Object.fromEntries([\'render\',\'execute\',\'reset\',\'getResponse\'].map(k => [k, typeof hcaptcha[k]])) : {}),\n      responseLengths: [...document.querySelectorAll(\'[name="h-captcha-response"],[name="g-recaptcha-response"]\')]\n        .map(e => ({name: e.name, length: e.value.length})),\n      checkbox: read(() => {\n        const e = document.querySelector(\'#checkbox[role="checkbox"],[role="checkbox"]\');\n        return e ? {role: e.getAttribute("role"), checked: e.getAttribute("aria-checked"),\n          label: e.getAttribute("aria-label"), rect: rect(e)} : null;\n      })},\n    scripts: [...document.scripts].map(e => ({src: e.src, type: e.type, async: e.async})),\n    frames: [...document.querySelectorAll("iframe")].map(e => ({src: e.src, title: e.title,\n      rect: read(() => rect(e)), display: read(() => getComputedStyle(e).display),\n      visibility: read(() => getComputedStyle(e).visibility)})),\n    bodyText: text(document.body).replace(/\\s+/g, \' \').trim().slice(0, 2500),\n    resources: read(() => performance.getEntriesByType("resource").map(e => ({\n      name: e.name, initiatorType: e.initiatorType, duration: e.duration,\n      transferSize: e.transferSize, responseEnd: e.responseEnd}))),\n    errors: globalThis.__environmentErrors || []\n  };\n})()\n'

CONFIG = {'navigator': {'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:158.0) Gecko/20100101 Firefox/158.0', 'appVersion': '5.0 (Windows)', 'platform': 'Win32', 'language': 'en-US', 'languages': ['en-US', 'en'], 'hardwareConcurrency': 12, 'maxTouchPoints': 0}, 'screen': {'width': 1366, 'height': 768, 'availWidth': 1366, 'availHeight': 720, 'availLeft': 0, 'availTop': 0, 'colorDepth': 24, 'pixelDepth': 24}, 'viewport': {'width': 1360, 'height': 876, 'devicePixelRatio': 1}, 'locale': {'timezone': 'Asia/Shanghai', 'osLocale': 'en-US'}}

def main():
    checks = device_memory_checks(Context)
    checks.update(memory_environment_checks(Context, MEMORY_SNAPSHOT))
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
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.put_resource('https://early.fixture.test/',
                '<script type="module">throw new Error("early module fixture")</script>',
                headers=[['Content-Type','text/html']])
            ctx.navigate('https://early.fixture.test/')
            console = ctx.console_log()
            checks['early_navigation_module_error_retained'] = dict(passed=any(
                e.get('level') == 'error' and 'early module fixture' in e.get('text','')
                and 'https://early.fixture.test/' in e.get('stack',[]) for e in console), console=console)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.put_resource('https://early.fixture.test/',
                '<script type="module">throw new Error("early frame fixture")</script>',
                headers=[['Content-Type','text/html']])
            ctx.load_page('https://fixture.test/', '<iframe src="https://early.fixture.test/"></iframe>')
            ctx.advance(10, max_tasks=1000)
            console = ctx.console_log()
            checks['early_frame_module_error_retained'] = dict(passed=any(
                e.get('level') == 'error' and 'early frame fixture' in e.get('text','')
                for e in console), console=console)
        with Context(timeout=30, proxy='http://127.0.0.1:9') as ctx:
            ctx.put_resource('https://early.fixture.test/',
                '<script>addEventListener("error",e=>e.preventDefault())</script>'
                '<script type="module">throw new Error("cancelled module fixture")</script>',
                headers=[['Content-Type','text/html']])
            ctx.navigate('https://early.fixture.test/')
            console = ctx.console_log()
            checks['cancelled_module_error_not_reported'] = dict(passed=not any(
                'cancelled module fixture' in e.get('text','') for e in console), console=console)
    except Exception as exc:
        checks['early_module_error_execution'] = dict(passed=False, error=str(exc))
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
