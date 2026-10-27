"""Read one observed public archive prefix; do not guess archive filenames."""
import json,urllib.request,urllib.parse,xml.etree.ElementTree as ET
from mtr_project.paths import ROOT,write_json


def main():
    folder=ROOT/'runs/project-v2/alignment-review-v1';parent=json.loads((folder/'official-index-probe.json').read_text())
    prefix=next(x for x in parent['prefixes'] if x.endswith('/train_set/'))
    url='https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/?'+urllib.parse.urlencode({'list-type':'2','prefix':prefix,'max-keys':1000})
    with urllib.request.urlopen(url,timeout=30) as response:
        status=response.status;body=response.read(1048577)
    if len(body)>1048576:raise ValueError('Index response exceeds1MiB')
    root=ET.fromstring(body);ns={'s3':'http://s3.amazonaws.com/doc/2006-03-01/'}
    objects=[{'key':x.findtext('s3:Key',namespaces=ns),'size':int(x.findtext('s3:Size',namespaces=ns))} for x in root.findall('s3:Contents',ns)]
    result={'source_url':url,'http_status':status,'response_bytes':len(body),'objects':objects,'is_truncated':root.findtext('s3:IsTruncated',namespaces=ns),
        'next_continuation_record_id':root.findtext('s3:NextContinuationRecordId',namespaces=ns)}
    write_json(folder/'official-train-index.json',result)
    print(json.dumps({'objects':len(objects),'is_truncated':result['is_truncated'],'first_objects':objects[:12],'last_objects':objects[-5:]},indent=2))


if __name__=='__main__':main()
