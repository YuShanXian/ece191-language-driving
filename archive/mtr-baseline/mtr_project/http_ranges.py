"""Single byte ranges for seeking locally archived video, no multipart support."""
import re

def byte_range(header,size):
    if size<=0:raise ValueError('Empty file')
    if header is None:return 0,size-1,False
    match=re.fullmatch(r'bytes=(\d*)-(\d*)',header)
    if match is None or not any(match.groups()):raise ValueError('Invalid range')
    left,right=match.groups()
    if not left:
        length=int(right)
        if length<=0:raise ValueError('Invalid suffix range')
        return max(0,size-length),size-1,True
    start=int(left);end=min(int(right),size-1) if right else size-1
    if not 0<=start<=end<size:raise ValueError('Range outside file')
    return start,end,True
