"""Render the existing review samples with readable row spacing; no video decoding."""
import json
from pathlib import Path
from PIL import Image
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from mtr_project.paths import ROOT,sha256,write_json


def main():
    base=ROOT/'runs/project-v2/alignment-review-v1';packet_path=base/'review-packet.json';packet=json.loads(packet_path.read_text())
    for name,digest in packet['artifact_sha256'].items():
        if sha256(base/name)!=digest:raise ValueError('Original review artifact changed: '+name)
    if len(packet['requests'])!=12 or packet['independent_raw_image_confirmation']:raise ValueError('Unexpected review packet scope')
    outputs={}
    for clip in packet['specification']['clips']:
        rows=[r for r in packet['requests'] if r['clip']==clip['clip']]
        fig,axes=plt.subplots(2,3,figsize=(15,9.3))
        fig.suptitle(f'{clip["annotation_id"]}: video samples awaiting original CAM_F0 images',fontsize=15,y=.97)
        for ax,row in zip(axes.flat,rows):
            with Image.open(base/row['decoded_sample']) as img:ax.imshow(img)
            ax.axis('off');ax.set_title(f'Video frame {row["video_frame_zero_based"]} / GPS row {row["gps_row_zero_based"]}\nGPS {row["gps_elapsed_s"]:.3f}s; camera offset {row["camera_offset_us"]/1000:.1f}ms',fontsize=10,pad=12)
        fig.subplots_adjust(left=.02,right=.98,bottom=.13,top=.87,hspace=.38,wspace=.05)
        fig.text(.02,.035,'Decoded video frames, NOT raw camera images. Expected filenames come from DB lookup.\nSpot checks can reveal mismatches; even 12 matching samples would not certify every video frame.',fontsize=10)
        output=base/clip['clip']/'contact-sheet-readable.png';fig.savefig(output,dpi=150);plt.close(fig);outputs[str(output.relative_to(base))]=sha256(output)
    page=base/'index.html';page.write_text(page.read_text().replace('/contact-sheet.png','/contact-sheet-readable.png'),encoding='utf-8');outputs['index.html']=sha256(page)
    request_file=base/'requested-raw-filenames.txt'
    if request_file.read_text().splitlines()!=[r['raw_filename_from_database'] for r in packet['requests']]:raise ValueError('Raw-image request list changed')
    write_json(base/'presentation-receipt.json',{'packet_sha256':sha256(packet_path),'generator_sha256':sha256(__file__),
        'outputs':outputs,'raw_request_list_sha256':sha256(request_file),'scope':'Readable rendering of existing samples only. No originals received or matched.'})
    print(json.dumps({'requests':len(packet['requests']),'figures':len(outputs)-1,'originals_received':0,'report':str(page)},indent=2))


if __name__=='__main__':main()
