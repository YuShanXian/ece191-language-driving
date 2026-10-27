"""Export decoded video samples and exact DB camera filenames for independent review."""
import csv,html,json,sqlite3
from pathlib import Path,PurePosixPath
import imageio_ffmpeg
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,sha256,write_json
from mtr_project.annotations import load_release
from mtr_project.video_alignment import validate_camera_mapping


def main():
    specification=ROOT/'config/alignment-review-v1.json';spec=json.loads(specification.read_text())
    dest=ROOT/'runs/project-v2/alignment-review-v1'
    if dest.exists():raise ValueError('Preserve existing review packet; use a separate version for changes')
    labels,release=load_release(ROOT/'references/release_annotationsV1.csv');labels={x.annotation_id:x for x in labels}
    sources={str(specification.relative_to(ROOT)):sha256(specification),str(Path(__file__).relative_to(ROOT)):sha256(__file__),
        str(Path(release['file']).relative_to(ROOT)):release['sha256']}
    sources.update({name:sha256(ROOT/name) for name in ['scripts/mtr_project/annotations.py','scripts/mtr_project/video_alignment.py']})
    jobs=[];requests=[];missing=[]
    # Resolve every intended image before writing outputs. Filenames come from DB rows, never guessed URLs.
    for item in spec['clips']:
        clip=item['clip'];annotation=labels[item['annotation_id']]
        if annotation.clip_id!=clip:raise ValueError('Annotation belongs to another clip')
        base=ROOT/'runs/project-v2/video-alignment'/clip;audit_path=base/'camera-lookup-audit.json';audit=json.loads(audit_path.read_text())
        gps=ROOT/'data/doplan'/clip/'gps.csv';video=gps.with_name('F0.mp4');db=ROOT/'data/nuplan/db'/f'{clip}.db'
        if sha256(gps)!=audit['source_sha256']['gps'] or sha256(video)!=audit['source_sha256']['video']:
            raise ValueError('Video/GPS changed since camera lookup audit')
        with gps.open() as stream:rows=list(csv.DictReader(stream))
        mapping=validate_camera_mapping(audit,[int(r['timestamp_us']) for r in rows])
        frames=item['video_frames_zero_based']
        if frames!=sorted(set(frames)) or not frames or frames[0]<0 or frames[-1]>=len(mapping):raise ValueError('Invalid selected frames')
        selected=[]
        with sqlite3.connect(db.as_uri()+'?mode=ro',uri=True) as conn:
            for frame in frames:
                match=mapping[frame];timestamp=match['timestamp_us'];gps_row=match['gps_row_zero_based']
                candidates=conn.execute('SELECT img.timestamp,img.filename_jpg,hex(img.record_id) FROM image img JOIN camera cam ON cam.record_id=img.camera_record_id WHERE cam.channel=? AND img.timestamp BETWEEN ? AND ? ORDER BY img.timestamp',('CAM_F0',timestamp-50000,timestamp+50000)).fetchall()
                if len(candidates)!=1 or [candidates[0][0]]!=match['camera_timestamp_candidates']:raise ValueError('Database camera lookup differs from saved audit')
                camera_time,filename,record_id=candidates[0];path=PurePosixPath(filename)
                if path.is_absolute() or '..' in path.parts or '\\' in filename:raise ValueError('Unexpected raw-image relative path')
                entry={'clip':clip,'annotation_id':annotation.annotation_id,'instruction':annotation.instruction,
                    'annotation_interval_zero_based_half_open':[annotation.start_frame,annotation.end_frame],
                    'video_frame_zero_based':frame,'gps_row_zero_based':gps_row,'gps_timestamp_us':timestamp,
                    'gps_elapsed_s':(timestamp-int(rows[0]['timestamp_us']))/1e6,'camera_timestamp_us':camera_time,
                    'camera_offset_us':camera_time-timestamp,'camera_channel':'CAM_F0','image_record_id_hex':record_id,
                    'raw_filename_from_database':filename,'decoded_sample':f'{clip}/video-frame-{frame:05d}.png',
                    'raw_image_received':False,'independent_match_status':'not_checked_original_image_missing'}
                selected.append(entry);requests.append(entry)
            for absent in audit['missing_camera_lookup_rows']:
                timestamp=absent['timestamp_us']
                count=conn.execute('SELECT COUNT(*) FROM image img JOIN camera cam ON cam.record_id=img.camera_record_id WHERE cam.channel=? AND img.timestamp BETWEEN ? AND ?',('CAM_F0',timestamp-50000,timestamp+50000)).fetchone()[0]
                if count:raise ValueError('Previously missing camera row now has a match')
                missing.append({'clip':clip,**absent,'raw_image_requested':False,'reason':'No CAM_F0 DB record within SDK +/-50ms; no frame invented'})
        sources.update({str(p.relative_to(ROOT)):sha256(p) for p in [gps,video,db,audit_path]})
        jobs.append((clip,video,selected))
    dest.mkdir();write_json(dest/'specification.json',spec)
    for clip,video,selected in jobs:
        print('EXTRACT REVIEW FRAMES',clip,flush=True);folder=dest/clip;folder.mkdir();wanted={r['video_frame_zero_based']:r for r in selected};images={}
        reader=imageio_ffmpeg.read_frames(str(video),pix_fmt='rgb24');metadata=next(reader);width,height=metadata['size']
        try:
            for index,raw_pixels in enumerate(reader):
                if index in wanted:
                    pixels=np.frombuffer(raw_pixels,dtype=np.uint8).reshape(height,width,3)
                    output=dest/wanted[index]['decoded_sample'];Image.fromarray(pixels).save(output)
                    wanted[index]['decoded_sample_sha256']=sha256(output);images[index]=pixels
                if index==max(wanted):break
        finally:reader.close()
        if set(images)!=set(wanted):raise ValueError('Video ended before a requested frame')
        fig,axes=plt.subplots(2,3,figsize=(15,7.3));fig.suptitle(f'{selected[0]["annotation_id"]}: video samples awaiting original CAM_F0 images',fontsize=15)
        for ax,row in zip(axes.flat,selected):
            ax.imshow(images[row['video_frame_zero_based']]);ax.axis('off')
            ax.set_title(f'Video frame {row["video_frame_zero_based"]} / GPS row {row["gps_row_zero_based"]}\nGPS {row["gps_elapsed_s"]:.3f}s; camera offset {row["camera_offset_us"]/1000:.1f}ms',fontsize=10)
        fig.text(.02,.02,'These are decoded video frames, NOT raw camera images. Expected filenames come from DB lookup.\nSpot checks can reveal mismatches; even 12 successful matches would not certify every video frame.',fontsize=10)
        fig.tight_layout(rect=[0,.09,1,.94]);fig.savefig(folder/'contact-sheet.png',dpi=150);plt.close(fig)
    packet={'specification':spec,'requests':requests,'missing_camera_rows':missing,'source_sha256':sources,
        'requested_images':len(requests),'independent_raw_image_confirmation':False,'usable_for_confirmed_language_evaluation':False}
    packet['artifact_sha256']={str(p.relative_to(dest)):sha256(p) for p in sorted(dest.rglob('*.png'))}
    write_json(dest/'review-packet.json',packet)
    (dest/'requested-raw-filenames.txt').write_text('\n'.join(r['raw_filename_from_database'] for r in requests)+'\n',encoding='utf-8')
    sections=[]
    for clip,_,selected in jobs:
        table=''.join('<tr><td>'+str(r['video_frame_zero_based'])+'</td><td>'+str(r['gps_timestamp_us'])+'</td><td><code>'+html.escape(r['raw_filename_from_database'])+'</code></td><td>\u5f85\u6536\u5230\u539f\u56fe</td></tr>' for r in selected)
        sections.append('<h2>'+html.escape(selected[0]['annotation_id'])+'</h2><p>'+html.escape(clip)+'</p><p>'+html.escape(selected[0]['instruction'])+'</p><img src="'+clip+'/contact-sheet.png" alt="\u89c6\u9891\u793a\u4f8b\u5e27，\u5c1a\u672a\u4e0e\u539f\u59cb\u7167\u7247\u6bd4\u5bf9"><table><tr><th>\u89c6\u9891\u5e27</th><th>GPS \u65f6\u95f4\u6233 µs</th><th>\u6570\u636e\u5e93\u4e2d\u539f\u56fe\u8def\u5f84</th><th>\u72b6\u6001</th></tr>'+table+'</table>')
    document='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>doPlan \u539f\u56fe\u6838\u5bf9\u6750\u6599</title><style>body{max-width:1150px;margin:36px auto;padding:0 24px;font:16px/1.7 system-ui;color:#243b50}h1,h2{color:#147e83}img{width:100%}table{width:100%;border-collapse:collapse;font-size:13px}td,th{text-align:left;padding:8px;border-bottom:1px solid #ddd;overflow-wrap:anywhere}aside{padding:18px;background:#fff4e5}code{overflow-wrap:anywhere}</style><h1>doPlan → nuPlan：\u539f\u59cb\u7167\u7247\u6838\u5bf9\u6750\u6599</h1><aside>\u4e0b\u976212\u5f20\u662f\u5df2\u4e0b\u8f7d\u89c6\u9891\u4e2d\u7684\u753b\u9762，\u4e0d\u662f\u65b0\u83b7\u5f97\u7684\u539f\u59cb\u4f20\u611f\u5668\u7167\u7247。\u53f3\u4fa7\u6587\u4ef6\u540d\u6765\u81ea nuPlan \u6570\u636e\u5e93。\u5c1a\u672a\u8fdb\u884c\u72ec\u7acb\u56fe\u50cf\u6bd4\u5bf9，\u4e5f\u6ca1\u6709\u63d0\u9ad8\u73b0\u6709\u5bf9\u9f50\u7ed3\u8bba\u7684\u53ef\u4fe1\u7b49\u7ea7。</aside><p>\u8fd9\u4e9b\u5e27\u6309\u9996\u5c3e、\u6807\u6ce8\u7a97\u53e3\u8fb9\u754c、\u4e2d\u95f4\u70b9\u548c\u5df2\u6709MTR\u68c0\u67e5\u70b9\u9884\u5148\u9009\u53d6，\u672a\u6309\u753b\u9762\u662f\u5426\u5339\u914d\u6311\u9009。\u539f\u56fe\u5230\u624b\u540e\u5e94\u5bf9\u7167\u9053\u8def、\u8f66\u8f86\u4e0e\u65f6\u95f4\u987a\u5e8f，\u5e76\u4fdd\u7559\u4e0d\u5339\u914d\u7ed3\u679c。\u89c6\u9891\u53ef\u80fd\u6709\u538b\u7f29\u6216\u53e0\u52a0，\u4e0d\u80fd\u53ea\u6bd4\u8f83\u6587\u4ef6\u54c8\u5e0c。</p>'''+''.join(sections)+'''<h2>\u5c11\u4e00\u5e27\u7684\u8fb9\u754c</h2><p>\u7b2c\u4e8c\u6bb5 GPS \u7b2c1234\u884c（\u4ece0\u5f00\u59cb）\u5728SDK\u7684±50ms\u7a97\u53e3\u5185\u6ca1\u6709\u524d\u65b9\u76f8\u673a\u8bb0\u5f55，\u56e0\u6b64\u6ca1\u6709\u865a\u6784\u5bf9\u5e94\u7167\u7247\u6216\u89c6\u9891\u5e27。\u53ef\u8bf7\u53d1\u5e03\u8005\u786e\u8ba4\u5bfc\u51fa\u65f6\u662f\u5426\u8df3\u8fc7\u8fd9\u4e00\u884c。</p><h2>\u9700\u8981\u8865\u5145\u7684\u6750\u6599</h2><p>\u4f18\u5148\u83b7\u53d6\u4e0a\u8ff012\u4e2a\u51c6\u786e\u6587\u4ef6\u540d\u7684\u539f\u59cbCAM_F0\u7167\u7247，\u4ee5\u53ca\u53d1\u5e03\u89c6\u9891\u5b9e\u9645\u4f7f\u7528\u7684\u5bfc\u51fa\u811a\u672c\u7248\u672c/\u91c7\u6837\u548c\u8df3\u5e27\u89c4\u5219。\u6587\u4ef6\u540d\u6e05\u5355\u5728 requested-raw-filenames.txt；\u9010\u6761\u65f6\u95f4\u53ca\u6765\u6e90\u6307\u7eb9\u5728 review-packet.json。</p><p>\u5373\u4f7f12\u5904\u62bd\u67e5\u90fd\u5339\u914d，\u4e5f\u53ea\u80fd\u8bc1\u660e\u8fd9\u4e9b\u62bd\u67e5\u70b9；\u5b8c\u6574\u9010\u5e27\u8ba4\u8bc1\u4ecd\u9700\u66f4\u591a\u8bc1\u636e。\u672c\u6750\u6599\u4ec5\u5b58\u672c\u673a，\u6ca1\u6709\u5411\u5bfc\u5e08\u53d1\u9001\u6d88\u606f。</p></html>'''
    (dest/'index.html').write_text(document,encoding='utf-8')
    print(json.dumps({'packet':str(dest),'requested_images':len(requests),'missing_camera_rows':missing},indent=2))


if __name__=='__main__':main()
