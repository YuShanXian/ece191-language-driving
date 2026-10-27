"""Deterministic metadata-only challenge anchors, with explicit missing events."""
from bisect import bisect_left


def choose_windows(timestamps,tag_times,fractions):
    if len(timestamps)<163 or any(b<=a for a,b in zip(timestamps,timestamps[1:])):raise ValueError('Need increasing lidar timestamps')
    start,end=timestamps[0],timestamps[-1];selected={};unavailable=[]
    def append(requested,reason):
        at=bisect_left(timestamps,requested);index=min([i for i in (at-1,at) if 0<=i<len(timestamps)],key=lambda i:(abs(timestamps[i]-requested),i))
        failure=None
        if abs(timestamps[index]-requested)>30000:failure='No lidar anchor within30ms'
        elif index<42 or index+120>=len(timestamps):failure='Insufficient converter history/future coverage'
        else:
            sequence=timestamps[index-40:index+121:2]
            if any(abs(b-a-100000)>=2000 for a,b in zip(sequence,sequence[1:])):failure='Irregular converter sample timestamps'
        if failure:unavailable.append({'sampling':reason,'reason':failure,'requested_timestamp_us':requested});return
        key=timestamps[index]
        selected.setdefault(key,{'timestamp_us':key,'seconds_after_first_lidar':(key-start)/1e6,'sampling':[]})['sampling'].append(reason)
    for fraction in fractions:append(start+round((end-start)*fraction),{'kind':'fixed_fraction','fraction':fraction})
    for name,times in tag_times.items():
        eligible=sorted(t for t in times if start+4000000<=t<=end-4000000)
        if not eligible:unavailable.append({'sampling':{'kind':'official_tag','type':name},'reason':'No eligible tag with declared temporal coverage'});continue
        append(eligible[0]-2000000,{'kind':'official_tag','type':name,'tag_timestamp_us':eligible[0],'offset_seconds':-2.})
    return sorted(selected.values(),key=lambda r:r['timestamp_us']),unavailable
