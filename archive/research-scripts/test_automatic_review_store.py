import tempfile
from pathlib import Path
from automatic_review_store import save_review,read_reviews
with tempfile.TemporaryDirectory() as d:
 p=Path(d)/'reviews.json';assert read_reviews(p)['reviews']==[]
 save_review(p,{'scene':1,'command':2,'verdict':'pass','comment':'\u9053\u8def\u7f16\u53f7\u4e0d\u540c，\u4f46\u5b9e\u9645\u901a\u8fc7。'})
 save_review(p,{'scene':2,'command':0,'verdict':'uncertain','comment':'\u7a0d\u540e\u5224\u65ad'})
 save_review(p,{'scene':1,'command':2,'verdict':'pass','comment':'\u66f4\u65b0\u8bc4\u8bed'})
 rows=read_reviews(p)['reviews'];assert len(rows)==2 and rows[0]['comment']=='\u66f4\u65b0\u8bc4\u8bed' and rows[1]['comment']=='\u7a0d\u540e\u5224\u65ad'
 original=p.read_bytes()
 try:save_review(p,{'scene':8,'command':0,'verdict':'pass','comment':'bad'})
 except ValueError:pass
 else:raise AssertionError('invalid scene accepted')
 assert p.read_bytes()==original
 print('Persistence, independent updates, Unicode and invalid-input preservation passed; real user reviews untouched.')
