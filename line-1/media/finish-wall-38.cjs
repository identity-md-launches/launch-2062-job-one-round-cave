// Keep only the image editor's knotted cord on previously bare rock.
const fs = require('node:fs');
const crypto = require('node:crypto');
const {decode, encode, thumbnail} = require('./finish-wall.cjs');
const hash = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
const oldBytes = fs.readFileSync('artifacts/line-1/wall-v18.png');
const old = decode(oldBytes), edit = decode(fs.readFileSync('artifacts/line-1/wall-v19.png'));
if(old.width !== edit.width || old.height !== edit.height) throw Error('size changed');
const output = {...old, pixels: Buffer.from(old.pixels)};
const clamp = v => Math.max(0, Math.min(1,v));
function segment(x,y,ax,ay,bx,by) {
  const t=clamp(((x-ax)*(bx-ax)+(y-ay)*(by-ay))/((bx-ax)**2+(by-ay)**2));
  return Math.hypot(x-ax-t*(bx-ax),y-ay-t*(by-ay));
}
function mask(x,y) {
  // Loop, lower knot and two trailing ends; no prior pigment falls in this mask.
  const loop=Math.abs(Math.hypot((x-476)/15,(y-197)/20)-1)*15;
  const knot=Math.abs(Math.hypot((x-465)/12,(y-220)/15)-1)*12;
  const tails=Math.min(segment(x,y,455,228,425,273),segment(x,y,471,222,520,231),
                       segment(x,y,453,225,426,235));
  return clamp((10-Math.min(loop,knot,tails))/4);
}
let changed=0, protectedPixels=0, outsideChanged=0;
for(let y=0;y<old.height;y++) for(let x=0;x<old.width;x++) {
  const a=mask(x,y), at=(y*old.width+x)*3;
  if(!a) protectedPixels++;
  let differs=false;
  for(let c=0;c<3;c++) {
    output.pixels[at+c]=Math.round(old.pixels[at+c]*(1-a)+edit.pixels[at+c]*a);
    differs ||= output.pixels[at+c] !== old.pixels[at+c];
  }
  if(differs) changed++;
  if(!a && differs) outsideChanged++;
}
if(outsideChanged || changed<1000) throw Error('mask failed');
const png=encode(output), jpg=thumbnail(output);
if(!decode(png).pixels.equals(output.pixels)) throw Error('PNG roundtrip failed');
if(jpg.length>100000) throw Error('JPEG too large');
fs.writeFileSync('artifacts/line-1/wall-v19.png',png);
fs.writeFileSync('artifacts/line-1/wall.png',png);
fs.writeFileSync('dist/line-1/38.jpg',jpg);
const report={previous_sha256:hash(oldBytes),sha256:hash(png),format:'PNG',width:old.width,height:old.height,
 png_bytes:png.length,preview_format:'JPEG',preview_width:512,preview_height:512,preview_bytes:jpg.length,
 changed_pixels:changed,protected_pixels:protectedPixels,outside_mask_changed_pixels:outsideChanged,
 mask:'feathered cord loop, knot and trailing segments on bare upper rock',png_roundtrip_passed:true};
fs.writeFileSync('line-1/media-check-38.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
