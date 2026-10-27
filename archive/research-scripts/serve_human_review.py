from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json, mimetypes, re, threading, os
ROOT=Path("historical-project")
BASE=ROOT/"runs/project-v3/language-choice-v1/report-reviewed/human-review"
OUT=BASE/"round-2"
SOURCES={x["scene"]:x for x in json.loads((BASE/"real-camera/sources.json").read_text())}
LOCK=threading.Lock()
STATE=OUT/"reviews.json"
def blank():
 return {"round":2,"reviews":[{"scene":s,"command":c,"verdict":"","safety":"","reason":""} for s in range(1,8) for c in range(5)]}
class Handler(BaseHTTPRequestHandler):
 def reply(self,data,code=200):
  b=json.dumps(data,ensure_ascii=False).encode();self.send_response(code);self.send_header("Content-Type","application/json; charset=utf-8");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  url=self.path.split("?")[0]
  if url=="/api/state":
   with LOCK: self.reply(json.loads(STATE.read_text()) if STATE.exists() else blank())
   return
  if url=="/api/sources":self.reply(SOURCES);return
  if url in ["/","/index.html"]:p=OUT/"index.html"
  elif re.fullmatch(r"/plot/[1-7]/[0-4]",url):
   _,_,s,c=url.split("/");p=BASE/f"scene-{int(s):02d}-command-{c}.png"
  elif re.fullmatch(r"/video/[1-7]",url):p=ROOT/SOURCES[int(url.rsplit("/",1)[1])]["video"]
  else:self.send_error(404);return
  if not p.is_file():self.send_error(404);return
  size=p.stat().st_size;start=0;end=size-1;partial=False
  r=self.headers.get("Range")
  if r:
   m=re.fullmatch(r"bytes=(\d+)-(\d*)",r)
   if not m:self.send_error(416);return
   start=int(m[1]);end=min(int(m[2]) if m[2] else end,end);partial=True
   if start>end:self.send_error(416);return
  self.send_response(206 if partial else 200)
  self.send_header("Content-Type",mimetypes.guess_type(str(p))[0] or "application/octet-stream")
  self.send_header("Content-Length",str(end-start+1));self.send_header("Accept-Ranges","bytes")
  if partial:self.send_header("Content-Range",f"bytes {start}-{end}/{size}")
  self.end_headers()
  try:
   with p.open("rb") as f:
    f.seek(start);remaining=end-start+1
    while remaining:
     b=f.read(min(1024*256,remaining))
     if not b:break
     self.wfile.write(b);remaining-=len(b)
  except (BrokenPipeError,ConnectionResetError):pass
 def do_POST(self):
  if self.path!="/api/state":self.send_error(404);return
  if self.headers.get("Origin") not in (None,"http://localhost:8768","http://127.0.0.1:8768"):self.send_error(403);return
  if self.headers.get("X-Review-App")!="round-2":self.send_error(403);return
  try:
   n=int(self.headers.get("Content-Length","0"))
   if not 0<n<300000:raise ValueError()
   data=json.loads(self.rfile.read(n))
   rows=data["reviews"]
   if len(rows)!=35 or data["round"]!=2:raise ValueError()
   for i,r in enumerate(rows):
    if r["scene"]!=i//5+1 or r["command"]!=i%5:raise ValueError()
    if r["verdict"] not in ("","success","fail","uncertain"):raise ValueError()
    if r["safety"] not in ("","no_obvious_issue","concern","uncertain","na"):raise ValueError()
    if not isinstance(r["reason"],str) or len(r["reason"])>10000:raise ValueError()
   from datetime import datetime,timezone
   data["saved_at"]=datetime.now(timezone.utc).isoformat()
   with LOCK:
    tmp=STATE.with_suffix(".tmp");tmp.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding="utf-8");os.replace(tmp,STATE)
   self.reply({"saved":True,"saved_at":data["saved_at"]})
  except Exception:self.reply({"error":"\u4fdd\u5b58\u5931\u8d25：\u6570\u636e\u683c\u5f0f\u4e0d\u6b63\u786e"},400)
if __name__=="__main__":
 ThreadingHTTPServer(("127.0.0.1",8768),Handler).serve_forever()
