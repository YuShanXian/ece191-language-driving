export function sampleFrame(frames,time){
 if(!frames.length)return null;
 let lo=0,hi=frames.length-1;
 while(hi-lo>1){const m=(lo+hi)>>1;if(frames[m][0]<=time)lo=m;else hi=m;}
 const a=frames[lo],b=frames[hi],u=Math.max(0,Math.min(1,(time-a[0])/Math.max(.00001,b[0]-a[0])));
 return [time,a[1]+u*(b[1]-a[1]),a[2]+u*(b[2]-a[2]),a[3]+u*Math.atan2(Math.sin(b[3]-a[3]),Math.cos(b[3]-a[3])),
  Number.isFinite(a[4])&&Number.isFinite(b[4])?a[4]+u*(b[4]-a[4]):null,...(u===1?b:a).slice(5)];
}
export function formatTime(seconds){const tenths=Math.max(0,Math.round(seconds*10));return `${Math.floor(tenths/600)}:${((tenths%600)/10).toFixed(1).padStart(4,'0')}`;}
export function scored(review){return review?.score!=null||!!review?.verdict;}
