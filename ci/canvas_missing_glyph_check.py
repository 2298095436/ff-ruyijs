"""Uncovered Unicode characters draw without terminating the current JS task."""
from ruyijs import Context


with Context(timeout=25) as ctx:
    ctx.configure_clock('logical', epoch_ms=1700000000000)
    ctx.load_page('https://missing-glyph.test/', '''<!doctype html>
<canvas id="surface" width="240" height="80"></canvas><script>
window.ink=surface.getContext('2d');
window.nonempty=()=>{const d=ink.getImageData(0,0,240,80).data;
let count=0;for(let i=3;i<d.length;i+=4)if(d[i])count++;return count};
</script>''')
    # U+0378 and U+D7FF are unassigned; U+D800 is a lone UTF-16 surrogate.
    # U+10FFFF tests the supplementary missing-glyph advance as well.
    for point in (0x41, 0x0378, 0xD7FF, 0xD800, 0x10FFFF):
        for operation in ('fillText', 'strokeText'):
            result = ctx.eval('''(()=>{ink.clearRect(0,0,240,80);ink.font='6px sans-serif';
const value=String.fromCodePoint(''' + str(point) + ''');
const width=ink.measureText(value).width;let completed=false;
ink.''' + operation + '''(value,8,30);completed=true;
return {completed,width,pixels:nonempty()}})()''')
            assert result['completed'] and result['width'] > 0 and result['pixels'] > 0, (
                hex(point), operation, result)
    # A failure returned without a pending JS exception cannot be caught by
    # page try/catch. The timer must complete and resolve its ordinary Promise.
    ctx.eval('''window.finished=false;window.resolved=false;
new Promise(resolve=>setTimeout(()=>{
  try{ink.fillText(String.fromCodePoint(0xd7ff),8,30)}catch(e){throw e}
  finished=true;resolve();
},0)).then(()=>{resolved=true});void 0''')
    ctx.advance(10, max_tasks=100)
    assert ctx.eval('finished&&resolved') is True
    # Missing text still advances the following supported text by the same
    # metrics used for a split draw; neither glyph-zero nor a no-op is enough.
    result = ctx.eval('''(()=>{ink.clearRect(0,0,240,80);ink.font='20px sans-serif';
const prefix='A'+String.fromCodePoint(0xd7ff);
const x=8+ink.measureText(prefix).width;
ink.fillText(prefix+'B',8,40);
const actual=ink.getImageData(0,0,240,80).data;
ink.clearRect(0,0,240,80);ink.fillText('B',x,40);
const expected=ink.getImageData(0,0,240,80).data;
let compared=0,different=0;
for(let y=0;y<80;y++)for(let col=Math.ceil(x)+1;col<240;col++){
  const at=(y*240+col)*4;
  for(let c=0;c<4;c++){if(actual[at+c]!==expected[at+c])different++}
  if(expected[at+3])compared++;
}
return {compared,different}})()''')
    assert result['compared'] > 0 and result['different'] == 0, result
    # Exercise the color-font fallback path with a missing character present,
    # and the normal transform/clip path for the new missing-glyph record.
    result = ctx.eval('''(()=>{ink.clearRect(0,0,240,80);ink.save();
ink.beginPath();ink.rect(0,0,180,70);ink.clip();ink.translate(4,2);ink.scale(1.1,.9);
ink.shadowColor='rgba(0,0,0,.5)';ink.shadowBlur=2;
ink.fillText(String.fromCodePoint(0x1f600,0xd7ff,0x41),8,40,90);
ink.restore();return {pixels:nonempty(),png:surface.toDataURL().slice(0,22)}})()''')
    assert result['pixels'] > 0 and result['png'] == 'data:image/png;base64,', result
    assert ctx.eval('6*7') == 42

assert ctx.closed and ctx._process.returncode == 0
print('ok missing Unicode canvas fill/stroke, timer continuation, pixels, advances and shutdown', flush=True)
