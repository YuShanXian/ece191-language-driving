from pathlib import Path
p=Path('historical-project/scripts/report_centerline_planner_v1.py');s=p.read_text(encoding='utf-8-sig');s=s.replace("  if r['steering_rad']>.6:","  if r['timing']['peak_lateral_accel_mps2']>1.9:problems.append('\u5f2f\u9053\u6a2a\u5411\u52a0\u901f\u5ea6\u4ecd\u8d85\u51fa\u89c4\u5212\u8bbe\u5b9a')\n  if r['steering_rad']>.6:")
s=s.replace("'12 \u79d2\u5185\u5c1a\u672a\u786e\u8ba4\u5230\u8fbe\u76ee\u6807\u9053\u8def'","'\u672a\u901a\u8fc7\u5b8c\u6574\u76ee\u6807\u9053\u8def\u8d34\u5408\u68c0\u67e5'")
s=s.replace('12 \u79d2\u5185\u5230\u8fbe\u7a0b\u5e8f\u9009\u4e2d\u7684\u9053\u8def：','\u76ee\u6807\u9053\u8def\u8d34\u5408\u68c0\u67e5\u901a\u8fc7：').replace('\u7b80\u5316\u8f66\u8f86\u8ddf\u8e2a\u5230\u8fbe\u76ee\u6807：','\u7b80\u5316\u8f66\u8f86\u8ddf\u8e2a\u901a\u8fc7\u9053\u8def\u8d34\u5408\u68c0\u67e5：')
s=s.replace("  note=next(","  if not r['target_match']['matched'] and any(e['end_on_target_branch'] for e in r['target_match']['evidence']):conclusion='\u5df2\u8fdb\u5165\u51fa\u53e3\u8f66\u9053，\u4f46\u8f6c\u5f2f\u6bb5\u672a\u901a\u8fc7\u76ee\u6807\u9053\u8def\u8d34\u5408\u68c0\u67e5'\n  note=next(")
p.write_text(s,encoding='utf-8')
