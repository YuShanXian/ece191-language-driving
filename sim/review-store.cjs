'use strict';
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const verdicts=new Set(['','pass','needs_work','fail','uncertain']);
class ReviewStore {
 constructor(root){this.root=root;this.pending=Promise.resolve();}
 async read(id){try{return JSON.parse(await fs.readFile(path.join(this.root,id+'.json'),'utf8'));}catch(e){if(e.code==='ENOENT')return null;throw e;}}
 save(meta,input){
  const job=this.pending.then(async()=>{
   const rating=input.rating;
   if(!rating||!verdicts.has(rating.verdict)||!(rating.score===null||Number.isInteger(rating.score)&&rating.score>=1&&rating.score<=5)||typeof rating.notes!=='string'||rating.notes.length>12000)throw Object.assign(Error('Invalid review values'),{status:400});
   const commands=rating.commands||{},markers=rating.markers||[];
   if(Object.keys(commands).length>300||Object.values(commands).some(x=>!verdicts.has(x))||!Array.isArray(markers)||markers.length>100||markers.some(x=>!Number.isFinite(x.time)||x.time<0||x.time>meta.duration+.2||typeof x.note!=='string'||x.note.length>2000))throw Object.assign(Error('Invalid instruction ratings or time markers'),{status:400});
   const previous=await this.read(meta.id),revision=previous?.revision||0;
   if(input.expectedRevision!==revision)throw Object.assign(Error('This review changed in another tab. Reload the saved review before saving again.'),{status:409});
   const record={caseId:meta.id,caseHash:meta.source.sha256,revision:revision+1,updatedAt:new Date().toISOString(),rating:{score:rating.score,verdict:rating.verdict,notes:rating.notes,commands,markers}};
   await fs.mkdir(this.root,{recursive:true});
   await fs.appendFile(path.join(this.root,'history.jsonl'),JSON.stringify(record)+'\n');
   const temp=path.join(this.root,meta.id+'.'+crypto.randomUUID()+'.tmp');
   await fs.writeFile(temp,JSON.stringify(record,null,2));await fs.rename(temp,path.join(this.root,meta.id+'.json'));
   return record;
  });this.pending=job.catch(()=>{});return job;
 }
}
module.exports={ReviewStore};
