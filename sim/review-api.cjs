'use strict';
const fs=require('node:fs/promises'),path=require('node:path');
const {ReviewStore}=require('./review-store.cjs');
function createReviewApi({dataRoot,reviewRoot,json,body}){
 const store=new ReviewStore(reviewRoot);
 async function catalog(){return JSON.parse(await fs.readFile(path.join(dataRoot,'catalog.json'),'utf8'));}
 return async(req,res,url)=>{
  if(!url.pathname.startsWith('/api/review/'))return false;
  try{
   const index=await catalog(),id=url.searchParams.get('id'),meta=index.cases.find(c=>c.id===id);
   if(req.method==='GET'&&url.pathname==='/api/review/catalog'){
    const cases=await Promise.all(index.cases.map(async c=>{const r=await store.read(c.id);return {...c,review:r&&r.caseHash===c.source.sha256?{score:r.rating.score,verdict:r.rating.verdict,updatedAt:r.updatedAt}:null,staleReview:!!r&&r.caseHash!==c.source.sha256};}));
    json(res,200,{...index,cases});return true;
   }
   if(req.method==='GET'&&url.pathname==='/api/review/map'){
    const n=Number(url.searchParams.get('scene'));if(!Number.isInteger(n)||n<1||n>7)throw Object.assign(Error('Invalid scene'),{status:400});
    json(res,200,JSON.parse(await fs.readFile(path.join(dataRoot,'maps',n+'.json'),'utf8')));return true;
   }
   if(req.method==='GET'&&url.pathname==='/api/review/export'){
    const reviews=[];for(const c of index.cases){const r=await store.read(c.id);if(r)reviews.push({...r,title:c.title,version:c.version,scene:c.scene,practice:!!c.practice});}
    res.setHeader('Content-Disposition','attachment; filename="driving-human-reviews.json"');
    json(res,200,{exportedAt:new Date().toISOString(),reviews});return true;
   }
   if(!meta)throw Object.assign(Error('Unknown test case'),{status:404});
   if(req.method==='GET'&&url.pathname==='/api/review/case'){
    json(res,200,{case:JSON.parse(await fs.readFile(path.join(dataRoot,'cases',meta.id+'.json'),'utf8')),review:await store.read(meta.id)});return true;
   }
   if(req.method==='POST'&&url.pathname==='/api/review/rating'){
    if(req.headers.origin&&req.headers.origin!==`http://${req.headers.host}`)throw Object.assign(Error('Same-origin review saves only'),{status:403});
    if(!String(req.headers['content-type']).startsWith('application/json'))throw Object.assign(Error('JSON required'),{status:415});
    const input=await body(req);
    const data=JSON.parse(await fs.readFile(path.join(dataRoot,'cases',meta.id+'.json'),'utf8'));
    const ids=new Set(data.commands.map(c=>String(c.id)));
    if(Object.keys(input.rating?.commands||{}).some(k=>!ids.has(k)))throw Object.assign(Error('Unknown instruction'),{status:400});
    json(res,200,await store.save(meta,input));return true;
   }
   json(res,405,{error:'Method not allowed'});return true;
  }catch(e){json(res,e.status||500,{error:e.message});return true;}
 };
}
module.exports={createReviewApi};
