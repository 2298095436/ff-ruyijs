"""Privileged Worker channel failures are synchronous DOMExceptions."""
from ruyijs import Context


with Context(timeout=30) as ctx:
    ctx.configure_clock('logical', epoch_ms=1700000000000)
    ctx.load_page('https://worker-policy.test/', '<!doctype html><title>Worker policy</title>')
    result = ctx.eval('''(()=>{const rows=[];
for(const name of ['Worker','SharedWorker'])for(const url of [
  'chrome://unregistered.invalid/content', 'resource://missing-worker.js',
  '  ChRoMe://unregistered.invalid/content  ', 'ReSoUrCe://missing-worker.js']){
  let worker;
  try{worker=new window[name](url);rows.push({name,url,constructed:true});
    worker.terminate?.();worker.port?.close()}
  catch(error){rows.push({name,url,constructed:false,error:error.name,
    code:error.code,domException:error instanceof DOMException,message:error.message})}
}
return rows})()''')
    assert len(result) == 8
    for row in result:
        assert not row['constructed'] and row['error'] == 'SecurityError', row
        assert row['domException'] and row['code'] == 18, row
        if row['name'] == 'Worker':
            assert row['message'] == ('Worker constructor: Failed to load worker script at "' +
                                      row['url'] + '"'), row
        else:
            assert row['message'] == 'The operation is insecure.', row
    # Valid but unloadable ordinary URLs still construct a Worker and queue an
    # error. Do not turn all scheme/origin refusals into synchronous exceptions.
    ctx.eval('''window.asyncErrors=[];window.refused=[];
for(const name of ['Worker','SharedWorker'])for(const url of [
  'https://other.worker-policy.test/worker.js','about:blank','javascript:void 0']){
  const worker=new window[name](url);
  worker.onerror=()=>asyncErrors.push(name+':'+url);refused.push(worker);
}void 0''')
    assert ctx.eval('asyncErrors.length') == 0
    ctx.advance(10, max_tasks=100)
    assert ctx.eval('asyncErrors.length') == 6, ctx.eval('asyncErrors')
    assert ctx.net_log() == [], ctx.net_log()
    # Supported script startup and ordinary message delivery must keep working.
    ctx.eval('''window.reply=null;
window.good=new Worker(URL.createObjectURL(new Blob([
  'onmessage=e=>postMessage(e.data+2)'],{type:'text/javascript'})));
good.onmessage=e=>{reply=e.data;good.terminate()};good.postMessage(40);void 0''')
    for _ in range(20):
        ctx.advance(50, max_tasks=100)
        if ctx.eval('reply===42'):
            break
    assert ctx.eval('reply') == 42
    assert ctx.eval('6*7') == 42

assert ctx.closed and ctx._process.returncode == 0
print('ok Worker/SharedWorker privileged SecurityError, ordinary async refusals and Blob messaging', flush=True)
