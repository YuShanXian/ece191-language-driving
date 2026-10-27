"""One bounded, unaccessenticated read of the official public sensor archive index."""
import json,urllib.request,urllib.error,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from mtr_project.paths import ROOT,write_json


def main():
    url='https://motional-nuplan.s3.ap-northeast-1.amazonaws.com/?list-type=2&prefix=public%2Fnuplan-v1.1%2Fsensor_blobs%2F&delimiter=%2F&max-keys=100'
    report={'checked_utc':datetime.now(timezone.utc).isoformat(),'url':url,'method':'GET','accessenticated':False,'max_response_bytes':1048576}
    try:
        with urllib.request.urlopen(url,timeout=30) as response:
            report['http_status']=response.status;body=response.read(1048577)
        if len(body)>1048576:raise ValueError('Index response exceeded1MiB bound')
        root=ET.fromstring(body);ns={'s3':'http://s3.amazonaws.com/doc/2006-03-01/'}
        report['prefixes']=[x.text for x in root.findall('s3:CommonPrefixes/s3:Prefix',ns)]
        report['objects']=[{'key':x.findtext('s3:Key',namespaces=ns),'size':int(x.findtext('s3:Size',namespaces=ns))} for x in root.findall('s3:Contents',ns)]
        report['is_truncated']=root.findtext('s3:IsTruncated',namespaces=ns);report['response_bytes']=len(body)
    except urllib.error.HTTPError as exc:report.update(http_status=exc.code,error='Unaccessenticated public index request was rejected; no bypass attempted.')
    except (OSError,ValueError,ET.ParseError) as exc:report['error']=str(exc)
    write_json(ROOT/'runs/project-v2/alignment-review-v1/official-index-probe.json',report);print(json.dumps(report,indent=2))


if __name__=='__main__':main()
