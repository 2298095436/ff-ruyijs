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
    return checks


CONFIG = {'navigator': {'userAgent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:158.0) Gecko/20100101 Firefox/158.0', 'appVersion': '5.0 (Windows)', 'platform': 'Win32', 'language': 'en-US', 'languages': ['en-US', 'en'], 'hardwareConcurrency': 12, 'maxTouchPoints': 0}, 'screen': {'width': 1366, 'height': 768, 'availWidth': 1366, 'availHeight': 720, 'availLeft': 0, 'availTop': 0, 'colorDepth': 24, 'pixelDepth': 24}, 'viewport': {'width': 1360, 'height': 876, 'devicePixelRatio': 1}, 'locale': {'timezone': 'Asia/Shanghai', 'osLocale': 'en-US'}}

def main():
    checks = device_memory_checks(Context)
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
