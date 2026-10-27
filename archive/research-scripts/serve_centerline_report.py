from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import re,mimetypes
BASE=Path('historical-project/runs/project-v3/centerline-planner-v1')
class Handler(BaseHTTPRequestHandler):
 def do_GET(self):
  name=self.path.split('?')[0].lstrip('/') or 'index.html'
  if name!='index.html' and not re.fullmatch(r'scene-0[1-7](?:-command-[0-4]\.png|\.html)',name):self.send_error(404);return
  p=BASE/name
  if not p.is_file():self.send_error(404);return
  b=p.read_bytes();self.send_response(200);self.send_header('Content-Type',mimetypes.guess_type(str(p))[0] or 'application/octet-stream');self.send_header('Content-Length',str(len(b)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(b)
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8774),Handler).serve_forever()
