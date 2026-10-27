"""Conditional video-frame mapping; never equate GPS row number and frame index."""
from dataclasses import asdict
from statistics import median


def validate_camera_mapping(audit,gps_times):
    mapping=audit['conditional_frame_mapping']
    if not audit['expected_count_matches_video'] or len(mapping)!=audit['front_video_decoded_frames']:
        raise ValueError('Camera lookup and decoded video counts disagree')
    if audit['multiple_camera_matches_rows']:raise ValueError('Ambiguous camera matches')
    if len(gps_times)!=audit['gps_rows'] or any(b<=a for a,b in zip(gps_times,gps_times[1:])):
        raise ValueError('GPS timeline changed or is not strictly increasing')
    previous=-1
    for index,row in enumerate(mapping):
        gps=row['gps_row_zero_based']
        if row['video_frame_if_source_contract_holds']!=index or not previous<gps<len(gps_times):
            raise ValueError('Invalid camera frame ordering')
        if row['timestamp_us']!=gps_times[gps]:raise ValueError('Camera lookup timestamp disagrees with GPS')
        previous=gps
    missing={r['gps_row_zero_based'] for r in audit['missing_camera_lookup_rows']}
    if missing != set(range(len(gps_times)))-{r['gps_row_zero_based'] for r in mapping}:
        raise ValueError('Missing-frame accounting inconsistent')
    return mapping


def annotation_window(label,mapping,gps_times):
    result={'annotation':asdict(label),'status':'unresolved','usable_for_window_level_exploration':False,
            'usable_for_confirmed_language_evaluation':False,'usable_for_action_onset_or_compliance_evaluation':False,
            'mapping_basis':'Conditional inspected exporter and SDK camera lookup; not raw-image accessentication.',
            'alternatives':[]}
    start,end=label.start_frame,label.end_frame
    if not 0<=start<end<=len(mapping):return result
    last=mapping[end-1];inferred=end==len(mapping)
    if not inferred:boundary=mapping[end]['timestamp_us']
    else:
        next_gps=last['gps_row_zero_based']+1
        boundary=gps_times[next_gps] if next_gps<len(gps_times) else last['timestamp_us']+round(median(b-a for a,b in zip(gps_times,gps_times[1:])))
    duration=(boundary-mapping[start]['timestamp_us'])/1e6
    result['alternatives']=[{'video_index_offset':0,'status':'mapped',
        'start_timestamp_us':mapping[start]['timestamp_us'],'end_timestamp_us':boundary,
        'last_displayed_timestamp_us':last['timestamp_us'],'duration_sec':duration,
        'duration_error_sec':duration-label.duration_seconds,'end_boundary_inferred':inferred,'end_frame_exclusive':end}]
    if abs(duration-label.duration_seconds)<=.25:
        result.update(status='conditional_on_exporter_camera_lookup',usable_for_window_level_exploration=True)
    return result
