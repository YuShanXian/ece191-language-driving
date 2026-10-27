from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import re,mimetypes,json
from automatic_review_store import read_reviews,save_review
from mtr_candidate_review_store import save_candidates
BASE=Path('historical-project/runs/project-v3/automatic-road-v9')
REVIEWS=BASE/'human-review/reviews.json'
class Handler(BaseHTTPRequestHandler):
 def reply(self,value,status=200):
  b=json.dumps(value,ensure_ascii=False).encode();self.send_response(status);self.send_header('Content-Type','application/json; charset=utf-8');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_GET(self):
  name=self.path.split('?')[0].lstrip('/') or 'index.html'
  if name=='api/candidate-reviews':self.reply(read_reviews(BASE/'human-review/candidate-selections.json'));return
  if name=='api/candidate-data':self.reply(json.loads((BASE/'candidate-picker-data.json').read_text()));return
  if name=='api/reviews':self.reply(read_reviews(REVIEWS));return
  if name not in ('index.html','review.js','candidate-picker.js') and not re.fullmatch(r'scene-0[1-7](?:-command-[0-4]\.png|\.html)',name):self.send_error(404);return
  p=BASE/name
  if not p.is_file():self.send_error(404);return
  b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
 def do_POST(self):
  if self.path not in ('/api/review','/api/candidate-review'):self.send_error(404);return
  if self.headers.get('Origin') not in (None,'http://localhost:8773','http://127.0.0.1:8773'):self.send_error(403);return
  try:
   length=int(self.headers.get('Content-Length','0'))
   if not 0<length<=60000:raise ValueError('invalid body size')
   value=json.loads(self.rfile.read(length));row=save_candidates(BASE/'human-review/candidate-selections.json',value) if self.path=='/api/candidate-review' else save_review(REVIEWS,value);self.reply({'saved':row})
  except (ValueError,TypeError,json.JSONDecodeError) as e:self.reply({'error':str(e)},400)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8773),Handler).serve_forever()
