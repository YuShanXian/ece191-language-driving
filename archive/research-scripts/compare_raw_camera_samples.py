"""Independent pixel evidence for fixed camera/video samples, not blanket certification."""
import html
import json
from pathlib import Path
import imageio_ffmpeg
import numpy as np
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT, sha256, write_json


def thumbnail(image):
    return np.asarray(image.convert('L').resize((256,144),Image.Resampling.BILINEAR),dtype=np.float32)


def main():
    source=ROOT/'runs/project-v2/alignment-review-v1'
    packet_path=source/'review-packet.json';packet=json.loads(packet_path.read_text())
    output=ROOT/'runs/project-v2/raw-image-comparison-v1'
    if output.exists():raise ValueError('Preserve comparison output; use a new version')
    originals={};fingerprints={str(packet_path.relative_to(ROOT)):sha256(packet_path),str(Path(__file__).relative_to(ROOT)):sha256(__file__)}
    for group in [2,6]:
        path=source/f'camera-{group}-download-receipt.json';receipt=json.loads(path.read_text())
        if not receipt['complete'] or receipt['packet_sha256']!=sha256(packet_path):raise ValueError('Download incomplete or wrong review packet')
        fingerprints[str(path.relative_to(ROOT))]=sha256(path)
        for shard in receipt['shards']:
            for image in shard['matches']:
                path=ROOT/image['file']
                if sha256(path)!=image['sha256']:raise ValueError('Original image changed')
                originals[image['raw_filename_from_database']]=image
                fingerprints[str(path.relative_to(ROOT))]=image['sha256']
    if set(originals)!={r['raw_filename_from_database'] for r in packet['requests']}:raise ValueError('Image set differs from fixed review set')
    output.mkdir();results=[];sections=[]
    for clip in dict.fromkeys(r['clip'] for r in packet['requests']):
        rows=[r for r in packet['requests'] if r['clip']==clip]
        video=ROOT/'data/doplan'/clip/'F0.mp4'
        if sha256(video)!=packet['source_sha256'][str(video.relative_to(ROOT))]:raise ValueError('Video changed')
        fingerprints[str(video.relative_to(ROOT))]=sha256(video)
        raw_images=[Image.open(ROOT/originals[r['raw_filename_from_database']]['file']).convert('RGB') for r in rows]
        raw_small=np.stack([thumbnail(image) for image in raw_images])
        reader=imageio_ffmpeg.read_frames(str(video),pix_fmt='rgb24');metadata=next(reader);width,height=metadata['size']
        scores=[];expected={};selected={r['video_frame_zero_based'] for r in rows}
        try:
            for frame,raw in enumerate(reader):
                pixels=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,3)
                small=thumbnail(Image.fromarray(pixels))
                scores.append(np.mean(np.abs(raw_small-small),axis=(1,2)))
                if frame in selected:expected[frame]=pixels.copy()
        finally:reader.close()
        matrix=np.stack(scores);matrix_path=output/(clip+'-all-frame-mae.npy');np.save(matrix_path,matrix)
        fingerprint=sha256(matrix_path)
        fig,axes=plt.subplots(6,3,figsize=(14,17.3),layout='constrained')
        fig.suptitle(f'{rows[0]["annotation_id"]}: official original images vs doPlan video\nFixed six samples; differences amplified 8x. This is a spot check.',fontsize=14)
        clip_results=[]
        for column,(row,image) in enumerate(zip(rows,raw_images)):
            frame=row['video_frame_zero_based'];sample=source/row['decoded_sample']
            if sha256(sample)!=row['decoded_sample_sha256'] or not np.array_equal(np.asarray(Image.open(sample).convert('RGB')),expected[frame]):
                raise ValueError('New video decode differs from fixed review frame')
            pixels=expected[frame]
            comparable=np.asarray(image.resize((width,height),Image.Resampling.BILINEAR),dtype=np.float32)
            difference=comparable-pixels.astype(np.float32);mse=float(np.mean(difference**2));mae=float(np.mean(np.abs(difference)))
            psnr=None if mse==0 else float(10*np.log10(255**2/mse))
            ranking=np.argsort(matrix[:,column],kind='stable');best=int(ranking[0])
            score=float(matrix[frame,column]);ties=np.flatnonzero(np.isclose(matrix[:,column],score,rtol=0,atol=1e-6)).tolist()
            neighbors=[{'frame':n,'thumbnail_mae':float(matrix[n,column])} for n in range(max(0,frame-5),min(len(matrix),frame+6))]
            record={**row,'original':originals[row['raw_filename_from_database']],
                    'original_size':list(image.size),'video_size':[width,height],'comparison_resize':'PIL bilinear only if dimensions differ',
                    'rgb_mae_0_to_255':mae,'rgb_psnr_db':psnr,'thumbnail_grayscale_mae':score,
                    'best_global_frame':best,'expected_minus_best_frames':frame-best,
                    'strictly_better_frame_count':int(np.count_nonzero(matrix[:,column]<score-1e-6)),
                    'frames_tied_with_expected':ties,'top_five_global_matches':[{'frame':int(n),'thumbnail_mae':float(matrix[n,column])} for n in ranking[:5]],
                    'nearby_frames':neighbors,'decoded_video_frames':len(matrix),'score_matrix_sha256':fingerprint,
                    'raw_image_received':True,'independent_match_status':'pixel_evidence_computed_pending_visual_review',
                    'full_video_certified':False,'usable_for_confirmed_language_evaluation':False}
            results.append(record);clip_results.append(record)
            for ax,data,title in zip(axes[column],[np.asarray(image),pixels,np.clip(np.abs(difference)*8,0,255).astype(np.uint8)],
                                     [f'Official CAM_F0 / frame {frame}',f'doPlan video / frame {frame}',f'8x difference; MAE {mae:.2f}; best frame {best}']):
                ax.imshow(data);ax.axis('off');ax.set_title(title,fontsize=10)
        figure=output/(clip+'-comparison.png');fig.savefig(figure,dpi=130);plt.close(fig)
        table=''.join(f'<tr><td>{r["video_frame_zero_based"]}</td><td>{r["best_global_frame"]}</td><td>{r["rgb_mae_0_to_255"]:.3f}</td><td>{r["rgb_psnr_db"]:.2f}</td><td>{r["strictly_better_frame_count"]}</td></tr>' for r in clip_results)
        sections.append(f'<h2>{html.escape(rows[0]["annotation_id"])}</h2><p>{html.escape(clip)}</p><img src="{figure.name}" alt="Original image, video frame and amplified difference"><table><tr><th>\u9884\u671f\u89c6\u9891\u5e27</th><th>\u5168\u7247\u6700\u76f8\u4f3c\u5e27</th><th>RGB\u5e73\u5747\u5dee\u503c /255</th><th>PSNR dB</th><th>\u6bd4\u9884\u671f\u5e27\u66f4\u76f8\u4f3c\u7684\u5e27\u6570</th></tr>{table}</table>')
        print(json.dumps({'clip':clip,'frames':len(matrix),'comparisons':[{'expected':r['video_frame_zero_based'],'best':r['best_global_frame'],'mae':r['rgb_mae_0_to_255'],'psnr':r['rgb_psnr_db']} for r in clip_results]},indent=2),flush=True)
    report={'method':'Exact requested original JPEGs independently fetched from official S3 TAR. Compare every decoded video frame at 256x144 grayscale using mean absolute difference; report full-resolution RGB error at preselected expected frames. No tuned acceptance threshold.',
            'source_sha256':fingerprints,'samples':results,'sample_count':len(results),'visual_review_completed':False,
            'full_video_certified':False,'usable_for_confirmed_language_evaluation':False,
            'limits':['Twelve predefined samples only, not all video frames.','Static/repeated frames can tie; pixel ranking alone is not a guarantee of unique timestamp.','Annotation interval is not instruction onset or a compliance label.','No existing conditional mapping flags are automatically promoted.']}
    report['artifact_sha256']={str(p.relative_to(output)):sha256(p) for p in output.iterdir() if p.is_file()}
    write_json(output/'comparison.json',report)
    (output/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>doPlan \u539f\u56fe\u5bf9\u7167</title><style>body{max-width:1250px;margin:36px auto;padding:0 24px;font:16px/1.7 system-ui;color:#23384a}h1,h2{color:#147e83}img{width:100%}table{border-collapse:collapse;width:100%}td,th{padding:8px;text-align:left;border-bottom:1px solid #ddd}aside{background:#fff4e5;padding:18px}</style><h1>nuPlan \u539f\u59cb\u7167\u7247 → doPlan \u89c6\u9891：12\u5904\u62bd\u67e5</h1><aside>\u539f\u56fe\u4ece\u5b98\u65b9\u76f8\u673a\u5305\u6309\u6570\u636e\u5e93\u4e2d\u7684\u51c6\u786e\u6587\u4ef6\u540d\u53d6\u5f97。\u8fd9\u662f\u9884\u5148\u56fa\u5b9a\u768412\u5904\u62bd\u67e5，\u4e0d\u4ee3\u8868\u6574\u6bb5\u89c6\u9891\u9010\u5e27\u8ba4\u8bc1，\u4e5f\u4e0d\u8bc1\u660e\u8bed\u8a00\u6307\u4ee4\u4f55\u65f6\u53d1\u51fa。\u539f\u6709\u6761\u4ef6\u6027\u6620\u5c04\u6ca1\u6709\u81ea\u52a8\u5347\u7ea7。</aside><p>\u6bcf\u5f20\u539f\u56fe\u4e0e\u6574\u6bb5\u89c6\u9891\u7684\u7f29\u7565\u56fe\u6bd4\u8f83，\u5bfb\u627e\u6700\u76f8\u4f3c\u7684\u5e27；\u540c\u65f6\u5c55\u793a\u9884\u671f\u5e27\u7684\u539f\u56fe、\u89c6\u9891\u548c\u653e\u5927\u5dee\u5f02。\u6ca1\u6709\u6839\u636e\u7ed3\u679c\u8c03\u6574\u901a\u8fc7\u9608\u503c。\u7cbe\u786e\u6765\u6e90、\u5168\u90e8\u5e27\u5f97\u5206\u548c\u9650\u5236\u8bb0\u5f55\u5728 comparison.json。</p>'+''.join(sections)+'</html>',encoding='utf-8')


if __name__=='__main__':main()
