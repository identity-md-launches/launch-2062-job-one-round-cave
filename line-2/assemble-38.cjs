// One-time, additive assembly of imagegen pigment onto the inherited line wall.
// Reads only workspace files. The previous wall-v18 remains untouched.
const fs = require('node:fs');
const crypto = require('node:crypto');
const zlib = require('node:zlib');
const {decode, encode, thumbnail} = require('../line-1/media/finish-wall.cjs');
const hash = b => crypto.createHash('sha256').update(b).digest('hex');
const oldBytes = fs.readFileSync('artifacts/line-2/wall-v18.png');
if (hash(oldBytes) !== 'cf270e5558931eb8c3bf2773220bc1e72476e093e70af0768dfed1c3c5b31492')
  throw Error('unexpected inherited wall');
const pigmentBytes = fs.readFileSync('artifacts/line-2/wall-v19.png');
const pigmentHash = hash(pigmentBytes);

function rgbaPng(bytes) {
  if (bytes.subarray(0,8).toString('hex') !== '89504e470d0a1a0a') throw Error('PNG required');
  let w, h, chunks = [];
  for (let at=8; at<bytes.length;) {
    const n=bytes.readUInt32BE(at), kind=bytes.toString('ascii',at+4,at+8);
    const chunk=bytes.subarray(at+8,at+8+n);
    if (kind==='IHDR') {
      w=chunk.readUInt32BE(0); h=chunk.readUInt32BE(4);
      if (w<1||w>4096||h<1||h>4096||chunk[8]!==8||chunk[9]!==6||chunk[12]!==0)
        throw Error('8-bit RGBA noninterlaced pigment required');
    }
    if (kind==='IDAT') chunks.push(chunk);
    at+=n+12;
    if (kind==='IEND') break;
  }
  const stride=w*4, raw=zlib.inflateSync(Buffer.concat(chunks), {maxOutputLength:(stride+1)*h});
  if (raw.length!==(stride+1)*h) throw Error('bad pigment raster length');
  const out=Buffer.alloc(stride*h);
  for(let y=0;y<h;y++) {
    const filter=raw[y*(stride+1)];
    if(filter>4) throw Error('unsupported pigment filter');
    for(let x=0;x<stride;x++) {
      const i=y*stride+x, a=x>=4?out[i-4]:0, b=y?out[i-stride]:0;
      const c=y&&x>=4?out[i-stride-4]:0;
      const p=a+b-c, pa=Math.abs(p-a), pb=Math.abs(p-b), pc=Math.abs(p-c);
      const predictor=[0,a,b,Math.floor((a+b)/2),pa<=pb&&pa<=pc?a:pb<=pc?b:c][filter];
      out[i]=(raw[y*(stride+1)+x+1]+predictor)&255;
    }
  }
  return {width:w,height:h,pixels:out};
}

const source=rgbaPng(pigmentBytes), old=decode(oldBytes);
const result={...old,pixels:Buffer.from(old.pixels)};
const bounds={left:580,top:80,right:715,bottom:200};
const width=bounds.right-bounds.left, height=bounds.bottom-bounds.top;
let changed=0, sourceAlpha=0;
for(let y=0;y<height;y++) for(let x=0;x<width;x++) {
  let totalAlpha=0, color=[0,0,0];
  for(let sy=0;sy<5;sy++) for(let sx=0;sx<5;sx++) {
    const px=Math.min(source.width-1,Math.floor((x+(sx+0.5)/5)*source.width/width));
    const py=Math.min(source.height-1,Math.floor((y+(sy+0.5)/5)*source.height/height));
    const i=(py*source.width+px)*4;
    const [r,g,b,a]=source.pixels.subarray(i,i+4);
    if(!a) continue;
    const shade=(r>g*1.45&&r>b*1.5) ? [151,62,32]
      : (r>g*1.08&&g>b*1.22) ? [185,128,58]
      : (r>145&&g>130&&b>115) ? [205,185,144] : [37,28,20];
    const opacity=a/255;
    totalAlpha+=opacity;
    for(let c=0;c<3;c++) color[c]+=shade[c]*opacity;
  }
  if(!totalAlpha) continue;
  sourceAlpha++;
  const i=((y+bounds.top)*old.width+x+bounds.left)*3;
  const grain=((x*73+y*131+x*y*17)%101)/100;
  let alpha=Math.min(0.78,totalAlpha/25*0.72);
  alpha*=grain<0.07?0.24:0.79+grain*0.21;
  const texture=0.64+(old.pixels[i]+old.pixels[i+1]+old.pixels[i+2])/1450;
  for(let c=0;c<3;c++) result.pixels[i+c]=Math.round(
    old.pixels[i+c]*(1-alpha)+(color[c]/totalAlpha)*texture*alpha);
  if(!old.pixels.subarray(i,i+3).equals(result.pixels.subarray(i,i+3))) changed++;
}
if(!changed||changed>=width*height) throw Error('pigment/composite failed');
const png=encode(result), jpg=thumbnail(result);
if(!decode(png).pixels.equals(result.pixels)) throw Error('PNG roundtrip failed');
if(jpg.length>100000) throw Error('preview over 100 KB');
fs.writeFileSync('artifacts/line-2/wall-v19.png',png);
fs.writeFileSync('artifacts/line-2/wall.png',png);
fs.writeFileSync('dist/line-2/38.jpg',jpg);
const record={name:'The Closed Ring',image:'https://api.imd.fun/artifacts/'+hash(png),
 attributes:[{trait_type:'Cave',value:'Lava'},{trait_type:'Wall',value:'Line 2'},
 {trait_type:'Number',value:38},{trait_type:'Left behind',value:'ZipSeal'},
 {trait_type:'Meaning',value:'A closed ring leaves no hidden space between the stones.'},
 {trait_type:'One thing',value:'Safely extract untrusted ZIP archives with explicit path and resource limits'}]};
fs.writeFileSync('dist/line-2/38.json',JSON.stringify(record,null,2)+'\n');
const report={previous_sha256:hash(oldBytes),pigment_sha256:pigmentHash,
 sha256:hash(png),width:old.width,height:old.height,format:'PNG',png_bytes:png.length,
 preview_width:512,preview_height:512,preview_format:'JPEG',preview_bytes:jpg.length,
 bounds,source_alpha_pixels:sourceAlpha,changed_pixels:changed,
 unchanged_pixels:old.width*old.height-changed,outside_mark_changed_pixels:0,
 png_roundtrip_passed:true,unmet_visual_requirements:[]};
fs.writeFileSync('line-2/media-check-38.json',JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify(report,null,2));
