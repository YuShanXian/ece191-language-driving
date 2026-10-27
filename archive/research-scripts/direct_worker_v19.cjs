const {spawn}=require('child_process');
let worker=null,seq=0,pending=new Map();
function start(){
 if(worker)return worker;
 const script=process.env.DEMO_WORKER_PATH;
 const command=script?`cd historical-project && PYTHONUNBUFFERED=1 PYTHONPATH=historical-project/scripts /opt/ece191-mtr/env/bin/python '${script.replaceAll("'","'\\''")}'`:'cd historical-project && PYTHONUNBUFFERED=1 bash run_wsl.sh scripts/direct_worker_v19.py';
 const p=spawn('wsl.exe',['bash','-lc',command],{windowsHide:true,stdio:['pipe','pipe','pipe']});worker=p;
 let buffer='';p.stdout.setEncoding('utf8');p.stdout.on('data',chunk=>{buffer+=chunk;let n;while((n=buffer.indexOf('\n'))>=0){const line=buffer.slice(0,n);buffer=buffer.slice(n+1);try{const x=JSON.parse(line),cb=pending.get(x.id);if(cb){pending.delete(x.id);cb(x.error?new Error(x.error):null,JSON.stringify(x.result),'')}}catch(e){console.error('Direct worker invalid response',e.message)}}});
 p.stderr.on('data',chunk=>console.error(String(chunk).slice(0,2000)));
 const fail=e=>{if(worker===p)worker=null;for(const cb of pending.values())cb(e,'','');pending.clear()};
 p.on('error',fail);p.on('exit',code=>fail(new Error('Direct worker exited: '+code)));return p;
}
exports.run=(request,callback)=>{const p=start(),id=++seq;const timer=setTimeout(()=>{if(pending.has(id))p.kill()},180000);pending.set(id,(...args)=>{clearTimeout(timer);callback(...args)});p.stdin.write(JSON.stringify({...request,id})+'\n')};
exports.start=start;
process.on('exit',()=>worker?.kill());
