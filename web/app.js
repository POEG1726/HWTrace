const colors=['#168d81','#e1774e','#597dc1','#b35b91','#b49538','#6d9e50','#8c6bb7','#d26869'];
const panels={live:{root:document.querySelector('#live'),selected:new Set(),session:null},history:{root:document.querySelector('#history'),selected:new Set(),session:null}};
const fmt=t=>{const d=new Date(t);return Number.isNaN(+d)?t:d.toLocaleString(undefined,{hour12:false,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',fractionalSecondDigits:3})};
const isTemperature=unit=>['°c','℃','�c','°f','℉','�f'].includes(unit.trim().toLowerCase());
const temperatureLimit=(unit,sensor,p)=>{if(!isTemperature(unit))return null;const stored=p.thresholds.get(key(sensor));const c=stored===undefined?(/(?:spd|dimm|dram|memory|memoria)/i.test(sensor.sensor_name+' '+sensor.reading_name)?50:80):stored;if(c===null)return null;return ['°f','℉','�f'].includes(unit.trim().toLowerCase())?c*9/5+32:c};
const key=s=>`${s.sensor_id}:${s.sensor_instance}:${s.reading_id}`;
const sensorLabel=s=>`${s.reading_name} [${key(s)}]`;
async function api(url){const r=await fetch(url);if(!r.ok)throw Error(`请求失败 (${r.status})`);return r.json()}
function el(tag,cls,text){const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e}
async function setup(p,id){if(!id){p.root.replaceChildren(el('div','empty','没有可显示的 session。'));return}if(p.session===id)return;p.session=id;p.selected=new Set();p.chartState=new Map();p.thresholds=new Map();p.hovered=false;p.root.replaceChildren(el('div','empty','正在读取传感器…'));try{p.sensors=await api('/api/sensors?session='+encodeURIComponent(id));if(p.session!==id)return;build(p)}catch(e){p.root.replaceChildren(el('div','empty error',e.message))}}
function build(p){p.root.replaceChildren();const work=el('div','workspace'),side=el('div','sensor-panel'),title=el('div','sensor-title','选择传感器'),count=el('span','count'),search=el('input','search'),list=el('div','sensor-list');search.placeholder='搜索名称或单位';search.setAttribute('aria-label','搜索传感器');title.append(count);side.append(title,search,list);p.plots=el('div','plots');work.append(side,p.plots);p.root.append(work);function renderList(){list.replaceChildren();count.textContent=`${p.selected.size} / ${p.sensors.length}`;const term=search.value.toLowerCase();for(const s of p.sensors){if(!`${s.sensor_name} ${s.reading_name} ${s.unit}`.toLowerCase().includes(term))continue;const label=el('label','sensor'),input=el('input');input.type='checkbox';input.checked=p.selected.has(key(s));const desc=el('span','',s.reading_name);desc.append(el('small','',`${s.sensor_name} · ${s.unit||'无单位'} · ${key(s)}`));input.onchange=()=>{if(input.checked&&p.selected.size>=50){input.checked=false;alert('最多同时选择 50 个传感器');return}input.checked?p.selected.add(key(s)):p.selected.delete(key(s));count.textContent=`${p.selected.size} / ${p.sensors.length}`;renderList();refresh(p,true)};label.append(input,desc);list.append(label);if(input.checked&&isTemperature(s.unit)){const threshold=el('label','sensor-threshold','高温阈值 °C '),field=el('input');field.type='number';field.step='1';field.placeholder='关闭';const v=temperatureLimit('°C',s,p);field.value=v===null?'':v;field.setAttribute('aria-label',s.reading_name+' 高温阈值 °C');field.onchange=()=>{const n=Number(field.value);p.thresholds.set(key(s),field.value.trim()!==''&&Number.isFinite(n)?n:null);refresh(p,true)};threshold.append(field);list.append(threshold)}}}search.oninput=renderList;renderList();refresh(p)}
async function refresh(p,force=false){
 if(!p.plots)return
 const generation=p.generation=(p.generation||0)+1,selected=[...p.selected],id=p.session;
 if(!selected.length){for(const state of p.chartState.values())state.view=null;p.plots.replaceChildren(el('div','empty','勾选左侧传感器以显示曲线。'));return}
 try{
  const groups=new Map();for(const k of selected){const sensor=p.sensors.find(x=>key(x)===k);if(!sensor)continue;const unit=sensor.unit||'无单位';if(!groups.has(unit))groups.set(unit,[]);groups.get(unit).push(sensor)}
  const results=await Promise.all([...groups].map(async ([unit,sensors])=>{const state=p.chartState.get(unit)||{average:1,zoom:[]};p.chartState.set(unit,state);const params=new URLSearchParams({session:id,average:state.average});sensors.forEach(s=>params.append('sensor',key(s)));if(state.zoom.length){const range=state.zoom.at(-1);params.set('start',Math.floor(range[0]));params.set('end',Math.ceil(range[1]))}const data=await api('/api/series?'+params);return [unit,data.map(d=>({...d,sensor:sensors.find(s=>key(s)===d.key),color:colors[selected.indexOf(d.key)%colors.length]}))]}));
  if(generation!==p.generation||id!==p.session)return;for(const child of [...p.plots.children])if(child.className==='empty')child.remove();const units=new Set(results.map(([unit])=>unit));for(const [unit,state] of p.chartState){if(state.view&&!units.has(unit)){state.view.box.remove();state.view=null}}for(const [unit,lines] of results)draw(p.plots,unit,lines,p)
 }catch(e){if(generation===p.generation)p.plots.replaceChildren(el('div','empty error',e.message))}
}
function draw(parent,unit,lines,p){
 const state=p.chartState.get(unit);
 if(!state.view){
  const box=el('div','plot'),head=el('div','plot-head'),legend=el('div','legend'),canvas=el('canvas'),tip=el('div','tooltip'),hint=el('div','plot-hint');tip.hidden=true;
  const controls=el('label','average-control','每组平均 '),average=el('input');average.type='number';average.min='1';average.max='10000';average.step='1';average.value=state.average;average.setAttribute('aria-label',unit+' 每组平均采样数');
  const applyAverage=()=>{const n=Number(average.value);if(!Number.isInteger(n)||n<1||n>10000){average.value=state.average;return}if(n!==state.average){state.average=n;refresh(p,true)}};
  average.onchange=applyAverage;average.onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();applyAverage()}};
  controls.append(average,document.createTextNode(' 个采样'));head.append(el('strong','',unit),legend,controls);box.append(head);
  if(isTemperature(unit))box.append(el('div','temperature-note','红色表示达到各传感器的高温阈值；阈值可在左侧调整（仅供视觉提示）'));
  box.append(hint,canvas,tip);parent.append(box);state.view={box,legend,canvas,tip,hint,lines:[],cursor:null,drag:null};
  const view=state.view;
  const position=e=>{const r=canvas.getBoundingClientRect();return {x:Math.max(65,Math.min(r.width-15,e.clientX-r.left)),y:Math.max(15,Math.min(r.height-32,e.clientY-r.top))}};
  canvas.onpointerdown=e=>{if(e.button!==0||!view.domain)return;view.cursor=position(e);view.drag={start:view.cursor.x,end:view.cursor.x,domain:[...view.domain]};canvas.setPointerCapture(e.pointerId);e.preventDefault();paint(view,state,unit,p)};
  canvas.onpointermove=e=>{view.cursor=position(e);if(view.drag)view.drag.end=view.cursor.x;paint(view,state,unit,p)};
  canvas.onpointerup=e=>{if(!view.drag)return;const drag=view.drag;drag.end=position(e).x;view.drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);if(Math.abs(drag.end-drag.start)>=8){const width=canvas.getBoundingClientRect().width;const time=x=>drag.domain[0]+(x-65)/(width-80)*(drag.domain[1]-drag.domain[0]);state.zoom.push([time(Math.min(drag.start,drag.end)),time(Math.max(drag.start,drag.end))]);refresh(p,true)}paint(view,state,unit,p)};
  canvas.addEventListener('wheel',e=>{
   if(!view.domain)return;
   const delta=Math.abs(e.deltaX)>Math.abs(e.deltaY)?e.deltaX:e.deltaY;
   if(!delta)return;e.preventDefault();
   const span=view.domain[1]-view.domain[0];
   const amount=Math.max(-0.8,Math.min(0.8,delta*(e.deltaMode===1?16:e.deltaMode===2?400:1)/500))*span;
   if(!amount)return;
   const range=[view.domain[0]+amount,view.domain[1]+amount];
   if(state.zoom.length)state.zoom[state.zoom.length-1]=range;else state.zoom.push(range);
   view.domain=range;
   clearTimeout(view.panTimer);view.panTimer=setTimeout(()=>refresh(p,true),100);
  },{passive:false});
  canvas.onpointercancel=()=>{view.drag=null;view.cursor=null;paint(view,state,unit,p)};
  canvas.onpointerleave=()=>{if(!view.drag){view.cursor=null;paint(view,state,unit,p)}};
  canvas.ondblclick=()=>{if(state.zoom.length){state.zoom.pop();refresh(p,true)}};
 }
 const view=state.view;view.lines=lines;view.legend.replaceChildren();for(const line of lines){const label=sensorLabel(line.sensor),range=Number.isFinite(line.min)&&Number.isFinite(line.max)?`最小 ${Number(line.min.toPrecision(6))} · 最大 ${Number(line.max.toPrecision(6))} ${unit==='无单位'?'':unit}`:'暂无数据';const x=el('span','legend-item',`${label}　${range}`);x.title=`${line.sensor.sensor_name} · ${label}`;x.style.setProperty('--color',line.color);view.legend.append(x)}
 view.hint.textContent=`拖动缩放，滚轮或触控板平移，双击回退${state.zoom.length?' · 已缩放':''}；${state.average>1?'显示实际采样分组平均值':'显示采样值'}；最大/最小值覆盖当前范围全部${state.average>1?'平均组':'采样'}`;
 paint(view,state,unit,p);
}
function paint(view,state,unit,p){
 const {canvas,tip,lines}=view,rect=canvas.getBoundingClientRect(),scale=devicePixelRatio||1,w=rect.width,h=rect.height,L=65,R=15,T=15,B=32;
 if(!w||!h)return;const cw=Math.round(w*scale),ch=Math.round(h*scale);if(canvas.width!==cw||canvas.height!==ch){canvas.width=cw;canvas.height=ch}
 const ctx=canvas.getContext('2d');ctx.setTransform(scale,0,0,scale,0,0);ctx.clearRect(0,0,w,h);
 const points=lines.flatMap(line=>line.points.map(point=>({t:Date.parse(point[0]),v:point[1]}))).filter(point=>Number.isFinite(point.t)&&Number.isFinite(point.v));
 if(!points.length){view.domain=null;tip.hidden=true;ctx.fillStyle='#81949d';ctx.fillText('此范围没有采样数据；双击回退',L,45);return}
 let minT=Infinity,maxT=-Infinity,minV=Infinity,maxV=-Infinity;for(const point of points){minT=Math.min(minT,point.t);maxT=Math.max(maxT,point.t);minV=Math.min(minV,point.v);maxV=Math.max(maxV,point.v)}
 if(view.drag)[minT,maxT]=view.drag.domain;if(minT===maxT)maxT++;if(minV===maxV){const pad=Math.abs(minV)*.05||1;minV-=pad;maxV+=pad}else{const pad=(maxV-minV)*.06;minV-=pad;maxV+=pad}view.domain=[minT,maxT];
 const X=t=>L+(t-minT)/(maxT-minT)*(w-L-R),Y=v=>T+(maxV-v)/(maxV-minV)*(h-T-B);
 ctx.font='11px Segoe UI';ctx.textAlign='right';ctx.fillStyle='#81949d';ctx.strokeStyle='#e4ecee';for(let i=0;i<=4;i++){const y=T+i*(h-T-B)/4;ctx.beginPath();ctx.moveTo(L,y);ctx.lineTo(w-R,y);ctx.stroke();ctx.fillText((maxV-i*(maxV-minV)/4).toPrecision(4),L-8,y+4)}ctx.textAlign='left';ctx.fillText(new Date(minT).toLocaleTimeString(),L,h-8);ctx.textAlign='right';ctx.fillText(new Date(maxT).toLocaleTimeString(),w-R,h-8);
 ctx.save();ctx.beginPath();ctx.rect(L,T,w-L-R,h-T-B);ctx.clip();
 for(const line of lines){const limit=temperatureLimit(unit,line.sensor,p);ctx.strokeStyle=line.color;ctx.lineWidth=1.5;ctx.beginPath();let prev=null;
  for(const point of line.points){const t=Date.parse(point[0]);if(!Number.isFinite(t)||!Number.isFinite(point[1])){prev=null;continue}const cur={x:X(t),y:Y(point[1]),v:point[1]};if(prev){ctx.moveTo(prev.x,prev.y);ctx.lineTo(cur.x,cur.y)}prev=cur}ctx.stroke();
  if(limit!==null){ctx.strokeStyle='#cf4937';ctx.lineWidth=2;ctx.beginPath();prev=null;for(const point of line.points){const t=Date.parse(point[0]);if(!Number.isFinite(t)||!Number.isFinite(point[1])){prev=null;continue}const cur={x:X(t),y:Y(point[1]),v:point[1]};if(prev&&(prev.v>=limit||cur.v>=limit)){let a=prev,b=cur;if(prev.v<limit){const f=(limit-prev.v)/(cur.v-prev.v);a={x:prev.x+(cur.x-prev.x)*f,y:Y(limit)}}else if(cur.v<limit){const f=(limit-prev.v)/(cur.v-prev.v);b={x:prev.x+(cur.x-prev.x)*f,y:Y(limit)}}ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y)}prev=cur}ctx.stroke();ctx.fillStyle='#cf4937';for(let i=0;i<line.points.length;i++){const point=line.points[i],t=Date.parse(point[0]),high=q=>q&&Number.isFinite(Date.parse(q[0]))&&Number.isFinite(q[1])&&q[1]>=limit;if(Number.isFinite(t)&&Number.isFinite(point[1])&&point[1]>=limit&&!high(line.points[i-1])&&!high(line.points[i+1])){ctx.beginPath();ctx.arc(X(t),Y(point[1]),2,0,Math.PI*2);ctx.fill()}}}
 }
 if(view.drag){ctx.fillStyle='rgba(22,141,129,.16)';ctx.fillRect(Math.min(view.drag.start,view.drag.end),T,Math.abs(view.drag.end-view.drag.start),h-T-B)}
 if(view.cursor){const {x,y}=view.cursor,target=minT+(x-L)/(w-L-R)*(maxT-minT);ctx.strokeStyle='#718b96';ctx.lineWidth=1;ctx.setLineDash([4,4]);ctx.beginPath();ctx.moveTo(x,T);ctx.lineTo(x,h-B);ctx.moveTo(L,y);ctx.lineTo(w-R,y);ctx.stroke();ctx.setLineDash([]);tip.replaceChildren(el('div','tooltip-time',`光标时间 ${fmt(new Date(target).toISOString())}`));
  for(const line of lines){let nearest=null,distance=Infinity;for(const point of line.points){const t=Date.parse(point[0]);if(!Number.isFinite(t)||!Number.isFinite(point[1]))continue;const d=Math.abs(t-target);if(d<distance){distance=d;nearest=point}}if(!nearest)continue;
   const row=el('div','tooltip-row'),dot=el('span','tooltip-dot'),name=el('span','tooltip-name',sensorLabel(line.sensor)),value=el('span','tooltip-value',`${nearest[1]} ${unit==='无单位'?'':unit}`);dot.style.setProperty('--color',line.color);name.title=`${line.sensor.sensor_name} · ${line.sensor.reading_name} · ${key(line.sensor)}`;row.append(dot,name,value);tip.append(row,el('div','tooltip-sample-time',`${state.average>1?`平均 ${nearest[2]} 个采样，结束`:'采样时间'} ${fmt(nearest[0])}`));ctx.beginPath();ctx.arc(X(Date.parse(nearest[0])),Y(nearest[1]),3,0,Math.PI*2);ctx.fillStyle=line.color;ctx.fill();ctx.strokeStyle='#fff';ctx.lineWidth=1;ctx.stroke();
  }tip.hidden=false;tip.style.left=Math.max(0,Math.min(x+14,view.box.clientWidth-tip.offsetWidth))+'px';tip.style.top=(canvas.offsetTop+Math.max(0,Math.min(y+14,canvas.clientHeight-tip.offsetHeight)))+'px';
 }else tip.hidden=true;ctx.restore();
}
let historyInitialized=false;async function update(){try{const sessions=await api('/api/sessions');document.querySelector('#status').textContent='数据库已连接';const latest=sessions[0];document.querySelector('#live-meta').textContent=latest?`开始 ${fmt(latest.started)} · 最后记录 ${fmt(latest.updated)}${latest.stopped?' · 已记录停止事件':''}`:'数据库中还没有记录';await setup(panels.live,latest?.session);const select=document.querySelector('#history-select'),old=select.value;select.replaceChildren();for(const s of sessions.slice(1)){const option=el('option','',`${fmt(s.started)} — ${fmt(s.updated)}  (${s.session})`);option.value=s.session;select.append(option)}if([...select.options].some(o=>o.value===old))select.value=old;else if(!select.options.length){const empty=el('option','','暂无过往记录');empty.value='';select.append(empty)}if(!historyInitialized||panels.history.session!==select.value){historyInitialized=true;await setup(panels.history,select.value)}if(panels.live.session===latest?.session)refresh(panels.live)}catch(e){document.querySelector('#status').textContent=e.message;document.querySelector('#status').className='error'}}document.querySelector('#history-select').onchange=e=>setup(panels.history,e.target.value);update();setInterval(update,5000);let resizeTimer;window.onresize=()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{refresh(panels.live);refresh(panels.history)},250)};


