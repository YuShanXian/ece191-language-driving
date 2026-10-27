"""Seekable bounded official ZIP reader with exact range and object identity checks."""
import io
import urllib.request


class VerifiedRemoteZip(io.RawIOBase):
    def __init__(self,url,budget,opener=urllib.request.urlopen):
        super().__init__();self.url=url;self.opener=opener;self.budget=budget;self.used=0;self.pos=0
        with opener(urllib.request.Request(url,method='HEAD'),timeout=30) as response:
            self.size=int(response.headers['Content-Length']);self.etag=response.headers.get('ETag')
        if not self.etag or self.size<=0:raise ValueError('Remote object identity unavailable')
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        if whence not in (0,1,2):raise ValueError('Invalid seek origin')
        target=(0 if whence==0 else self.pos if whence==1 else self.size)+offset
        if target<0:raise ValueError('Negative seek')
        self.pos=target;return target
    def read(self,n=-1):
        n=min(max(0,self.size-self.pos),n if n>=0 else max(0,self.size-self.pos))
        if n==0:return b''
        if n>64*1024**2 or self.used+n>self.budget:raise ValueError('Bounded ZIP read budget exceeded')
        start=self.pos;end=start+n-1
        request=urllib.request.Request(self.url,headers={'Range':f'bytes={start}-{end}','If-Match':self.etag})
        with self.opener(request,timeout=30) as response:
            if response.status!=206 or response.headers.get('ETag')!=self.etag or response.headers.get('Content-Range')!=f'bytes {start}-{end}/{self.size}':raise ValueError('Remote ZIP identity or byte range mismatch')
            data=response.read(n+1)
        self.used+=len(data)
        if len(data)!=n:raise ValueError('Remote ZIP length mismatch')
        self.pos+=n;return data
