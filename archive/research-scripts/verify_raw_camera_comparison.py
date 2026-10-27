"""Reopen local source images and pixel evidence without re-downloading archives."""
import json
from pathlib import Path
import numpy as np
from PIL import Image
from compare_raw_camera_samples import thumbnail
from probe_target_camera_archives import headers
from mtr_project.paths import ROOT, sha256, write_json


def main():
    folder=ROOT/'runs/project-v2/raw-image-comparison-v1';path=folder/'comparison.json';report=json.loads(path.read_text())
    packet_dir=ROOT/'runs/project-v2/alignment-review-v1'
    packet=json.loads((packet_dir/'review-packet.json').read_text())
    for name,digest in report['source_sha256'].items():
        if sha256(ROOT/name)!=digest:raise ValueError('Source changed: '+name)
    for name,digest in report['artifact_sha256'].items():
        if sha256(folder/name)!=digest:raise ValueError('Comparison artifact changed: '+name)
    expected={(r['clip'],r['video_frame_zero_based']):r for r in packet['requests']}
    actual={(r['clip'],r['video_frame_zero_based']):r for r in report['samples']}
    if len(actual)!=len(report['samples']) or set(actual)!=set(expected):raise ValueError('Fixed sample coverage differs')
    checked=[]
    for clip in dict.fromkeys(r['clip'] for r in report['samples']):
        rows=[r for r in report['samples'] if r['clip']==clip]
        matrix=np.load(folder/(clip+'-all-frame-mae.npy'),allow_pickle=False)
        if matrix.shape!=(rows[0]['decoded_video_frames'],len(rows)) or not np.isfinite(matrix).all():raise ValueError('Invalid score matrix')
        for column,row in enumerate(rows):
            original=row['original'];frame=row['video_frame_zero_based'];request=expected[(clip,frame)]
            if original['raw_filename_from_database']!=request['raw_filename_from_database']:raise ValueError('Wrong requested image')
            raw=ROOT/original['file'];sample=packet_dir/request['decoded_sample']
            if sha256(raw)!=original['sha256'] or sha256(sample)!=request['decoded_sample_sha256']:raise ValueError('Image changed')
            group=int(original['name'].split('/')[0].split('_')[-1])
            cache=packet_dir/'archive-ranges'/str(group)
            header_path=cache/f'{original["offset"]}-512.bin';receipt=json.loads(header_path.with_suffix('.json').read_text())
            header=header_path.read_bytes();entries=headers(header,original['offset'])
            if sha256(header_path)!=receipt['sha256'] or receipt['etag']!=original['archive_etag'] or receipt['url']!=original['archive_url']:raise ValueError('TAR source identity changed')
            if len(entries)!=1 or any(entries[0][k]!=original[k] for k in ['name','size','type','offset']):raise ValueError('Saved TAR member differs')
            if original['size']!=raw.stat().st_size:raise ValueError('Image length differs from TAR member')
            source_pixels=Image.open(raw).convert('RGB');video_pixels=Image.open(sample).convert('RGB')
            score=float(np.mean(np.abs(thumbnail(source_pixels)-thumbnail(video_pixels))))
            if not np.isclose(score,matrix[frame,column],atol=1e-6,rtol=0) or not np.isclose(score,row['thumbnail_grayscale_mae'],atol=1e-6,rtol=0):raise ValueError('Expected-frame pixel error differs')
            ranking=np.argsort(matrix[:,column],kind='stable')
            better=int(np.count_nonzero(matrix[:,column]<score-1e-6))
            if int(ranking[0])!=row['best_global_frame'] or better!=row['strictly_better_frame_count']:raise ValueError('Frame ranking differs')
            if row['full_video_certified'] or row['usable_for_confirmed_language_evaluation']:raise ValueError('Spot check improperly promoted')
            checked.append({'clip':clip,'frame':frame,'best_frame':int(ranking[0]),'strictly_better_count':better})
    result={'status':'passed_declared_local_evidence_checks','comparison_sha256':sha256(path),
            'verifier_sha256':sha256(__file__),'checked':checked,'count':len(checked),
            'scope':'Rechecked saved source hashes, requested filenames, exact TAR headers, original image bytes/length, expected pixel score and global ranking. Full video not decoded again; same metric implementation; no blanket certification.'}
    write_json(folder/'verification.json',result);print(json.dumps(result,indent=2))


if __name__=='__main__':main()
