const http=require('http'),fs=require('fs'),path=require('path'),{execFile}=require('child_process');
const root=process.env.ECE191_ROOT||path.resolve(__dirname,'..');
const canonical=path.join(root,'runs/project-v3/recording-demo-v1'),base=process.env.DEMO_BASE||canonical;
const port=Number(process.env.DEMO_PORT||8775);
const python=path.join(process.env.USERPROFILE,'.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe');
const catalog=()=>JSON.parse(fs.readFileSync(process.env.DEMO_CATALOG||path.join(root,'config/language-parser-v4/demo-models.json'),'utf8').replace(/^\uFEFF/,''));
const send=(r,s,x)=>{r.writeHead(s,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});r.end(JSON.stringify(x))};
const journal=path.join(base,'command-history.jsonl');
function record(event){fs.appendFileSync(journal,JSON.stringify({...event,time:new Date().toISOString()})+'\n','utf8');}
const worker=require('./direct_worker_v19.cjs');worker.start();
let parsing=false;
const validState=s=>s&&Array.isArray(s.xy)&&s.xy.length===2&&[...s.xy,s.heading,s.speed].every(Number.isFinite)&&s.speed>=0&&s.speed<=40&&(!('target_speed_mps' in s)||Number.isFinite(s.target_speed_mps)&&s.target_speed_mps>=0&&s.target_speed_mps<=15);
function run(request,r){worker.run(request,(err,out)=>{if(err)return send(r,502,{error:err.message});try{send(r,200,JSON.parse(out))}catch{send(r,502,{error:'Invalid planner response'})}})}
http.createServer((q,r)=>{
 if(q.method==='GET'){
  if(q.url==='/health')return send(r,200,{service:'ece191-driving-demo',status:'ok',pid:process.pid,uptime_seconds:Math.round(process.uptime())});
  if(q.url==='/history'){
   const rows=fs.existsSync(journal)?fs.readFileSync(journal,'utf8').trim().split('\n').filter(Boolean).map(x=>{try{return JSON.parse(x)}catch{return null}}).filter(Boolean):[];
   return send(r,200,rows.slice(-1000).reverse());
  }
  if(q.url==='/models')return send(r,200,catalog());
  const evidence={'/queue-results':'report.html','/queue-corpus.json':'tests/language-corpus.json','/queue-evidence.json':'results/semantic-replay-results.json'};
  if(evidence[q.url]){
   const file=path.join(root,'runs/project-v3/queue-v21',evidence[q.url]);
   if(!fs.existsSync(file))return send(r,404,{error:'Test report is being prepared'});
   r.writeHead(200,{'Content-Type':file.endsWith('.html')?'text/html; charset=utf-8':'application/json; charset=utf-8','Cache-Control':'no-store'});return r.end(fs.readFileSync(file));
  }
  const files={'/':'index.html','/data.json':'data.json','/continuous.json':'continuous.json','/continuous.js':'continuous.js','/queue.js':'queue.js','/drive-monitor.js':'drive-monitor.js','/queue-core.js':'queue-core.js','/benchmark':null};
  if(Object.hasOwn(files,q.url)){
   let file=q.url==='/benchmark'?path.join(root,'runs/project-v3/provider-benchmark-20261020/report.html'):path.join(base,files[q.url]);
   if(!fs.existsSync(file)&&files[q.url])file=path.join(canonical,files[q.url]);
   if(!fs.existsSync(file))return send(r,404,{error:'File not found'});
   r.writeHead(200,{'Content-Type':file.endsWith('.html')?'text/html; charset=utf-8':file.endsWith('.js')?'text/javascript; charset=utf-8':'application/json','Cache-Control':'no-store'});return r.end(fs.readFileSync(file));
  }
 }
 if(q.method!=='POST'||!['/parse','/direct','/queue/step','/queue/prepare','/history-event'].includes(q.url))return send(r,404,{error:'Not found'});
 if(q.headers.origin&&!['http://localhost:'+port,'http://127.0.0.1:'+port].includes(q.headers.origin))return send(r,403,{error:'Invalid origin'});
 let body='';q.on('data',x=>{body+=x;if(body.length>256000)q.destroy()});q.on('end',()=>{
  let req;try{req=JSON.parse(body)}catch{return send(r,400,{error:'Invalid JSON'})}
  if(q.url==='/history-event'){record({...req,source:'browser'});return send(r,200,{saved:true})}
  if(q.url==='/queue/prepare')return run({op:'prepare',plan:req.plan},r);
  if(!Number.isInteger(req.scene)||req.scene<1||req.scene>7||!validState(req.state)||!['free','safe'].includes(req.mode||'free'))return send(r,400,{error:'Invalid scene, current pose, speed or driving mode'});
  if(q.url==='/queue/step'){
   if(!req.stage||!Number.isFinite(req.remaining)||req.remaining<0||req.remaining>120||!Number.isFinite(req.elapsed)||req.elapsed<0||req.elapsed>3600)return send(r,400,{error:'Invalid stage or waiting budget'});
   return run({op:'queue',scene:req.scene,state:req.state,stage:req.stage,next_action:req.next_action,remaining:req.remaining,elapsed:req.elapsed,mode:req.mode||'free'},r);
  }
  if(q.url==='/direct'){
   const allowed=['go_straight','turn_left','turn_right','lane_change_left','lane_change_right','u_turn','reverse','pull_over','emergency_stop','cancel','resume','continuous_drive'];
   if(!allowed.includes(req.action))return send(r,400,{error:'Invalid direct action'});
   return run({...req,op:'direct'},r);
  }
  const c=catalog(),model=req.model||c.default;
  if(typeof req.instruction!=='string'||!req.instruction.trim()||req.instruction.length>1000||!c.models.some(m=>m.id===model&&m.enabled))return send(r,400,{error:'Invalid instruction or unavailable model'});
  if(parsing)return send(r,409,{error:'A language request is already running'});
  parsing=true;const started=Date.now();record({...req,status:'parsing'});
  execFile(python,[path.join(__dirname,'parser_backends.py'),'--model',model,'--instruction',req.instruction],{timeout:180000,maxBuffer:8*1024*1024,windowsHide:true,env:{...process.env,PYTHONIOENCODING:'utf-8'}},(err,out,stderr)=>{
   parsing=false;
   if(err){record({id:req.history_id,status:'parser_error',reason:err.message});return send(r,502,{error:stderr?.includes('provider usage limit reached')?'Selected model has reached its provider usage limit. Choose another configured model. The previous queue is preserved.':'Language parser failed; the previous queue was preserved'})}
   try{const parsed=JSON.parse(out);parsed.model_info.total_seconds=(Date.now()-started)/1000;record({id:req.history_id,instruction:req.instruction,status:parsed.status,actions:parsed.stages});send(r,200,parsed)}catch{send(r,502,{error:'Invalid parser response'})}
  });
 });
}).listen(port,'127.0.0.1',()=>console.log('Recording demo v21: http://localhost:'+port));
