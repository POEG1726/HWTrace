const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const requests = [];
const ctx = new Proxy({}, {get(o,k){if(!(k in o))o[k]=k==='getImageData'?()=>({}):()=>{};return o[k]},set(o,k,v){o[k]=v;return true}});
class Element {
 constructor(tag='div'){this.tag=tag;this.children=[];this.style={setProperty(){}};this.value='';this.clientHeight=480;this.clientWidth=800;this.offsetWidth=150;this.offsetHeight=80;this.offsetTop=30;}
 append(...items){for(const item of items){if(item&&typeof item==='object'){item.parent=this;this.children.push(item)}}}
 replaceChildren(...items){this.children=[];this.append(...items)}
 remove(){if(this.parent)this.parent.children=this.parent.children.filter(x=>x!==this)}
 addEventListener(name,fn){this['on'+name]=fn} setAttribute(){} setPointerCapture(){} hasPointerCapture(){return true} releasePointerCapture(){} getBoundingClientRect(){return {width:800,height:480,left:0,top:0}} getContext(){return ctx}
}
const document={querySelector:()=>new Element(),createElement:tag=>new Element(tag),createTextNode:()=>new Element('text')};
const fetch=async url=>{requests.push(url);const params=new URL('http://local'+url).searchParams;return {ok:true,json:async()=>[{key:'1:0:2',points:[['2026-01-01T00:00:00.000Z',40,1],['2026-01-01T00:01:00.000Z',50,1],['2026-01-01T00:02:00.000Z',60,1]]}]}};
const sandbox={document,window:{},fetch,URLSearchParams,devicePixelRatio:1,console,setTimeout,clearTimeout,setInterval(){},alert(){}};
let source=fs.readFileSync('web/app.js','utf8');source=source.replace('update();setInterval(update,5000);','');
vm.createContext(sandbox);vm.runInContext(source,sandbox);
(async()=>{
 const p={plots:new Element(),session:'s',selected:new Set(['1:0:2']),sensors:[{sensor_id:1,sensor_instance:0,reading_id:2,sensor_name:'CPU',reading_name:'CPU',unit:'°C'}],chartState:new Map(),thresholds:new Map()};sandbox.panel=p;
 const get=(tag,node=p.plots)=>{if(node.tag===tag)return node;for(const c of node.children){const v=get(tag,c);if(v)return v}};
 const run=()=>vm.runInContext('refresh(panel,true)',sandbox);
 await run();let canvas=get('canvas');assert.ok(canvas.onpointerdown);
 canvas.onpointerdown({button:0,clientX:120,clientY:100,pointerId:1,preventDefault(){}});const beforeDrag=requests.length;await vm.runInContext('refresh(panel)',sandbox);assert.equal(requests.length,beforeDrag+1,'refresh during drag');assert.equal(get('canvas'),canvas,'canvas must persist during refresh');assert.ok(p.chartState.get('°C').view.drag,'drag must persist during refresh');canvas.onpointerup({clientX:500,clientY:100,pointerId:1});await new Promise(r=>setTimeout(r,0));
 assert.ok(requests.at(-1).includes('start='),'zoom must request selected range');assert.equal(p.chartState.get('°C').zoom.length,1);
 canvas=get('canvas');const previous=p.chartState.get('°C').zoom.at(-1).slice();let prevented=false;canvas.onwheel({deltaX:0,deltaY:100,deltaMode:0,preventDefault(){prevented=true}});assert.ok(prevented);assert.ok(p.chartState.get('°C').zoom.at(-1)[0]>previous[0],'wheel must pan time range');clearTimeout(p.chartState.get('°C').view.panTimer);canvas.ondblclick();await new Promise(r=>setTimeout(r,0));assert.equal(p.chartState.get('°C').zoom.length,0);
 const input=get('input');input.value='3';input.onchange();await new Promise(r=>setTimeout(r,0));assert.match(requests.at(-1),/average=3/);
 canvas=get('canvas');canvas.onpointermove({clientX:200,clientY:100});const before=requests.length;await vm.runInContext('refresh(panel)',sandbox);assert.equal(requests.length,before+1,'hover must not block refresh');assert.equal(get('canvas'),canvas,'canvas must persist during hover refresh');assert.ok(p.chartState.get('°C').view.cursor,'cursor must persist during refresh');
 console.log('dashboard interaction checks passed');
})().catch(e=>{console.error(e);process.exitCode=1});
