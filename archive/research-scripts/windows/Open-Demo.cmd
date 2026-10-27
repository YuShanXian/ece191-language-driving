@echo off
chcp 65001 >nul
echo ECE191 \u672c\u5730\u6f14\u793a
echo \u6d4f\u89c8\u5668\u5730\u5740: http://localhost:8765
echo \u5982\u679c\u670d\u52a1\u5668\u5df2\u7ecf\u8fd0\u884c，\u76f4\u63a5\u4f7f\u7528\u6253\u5f00\u7684\u9875\u9762。
echo \u672c\u7a97\u53e3\u542f\u52a8\u7684\u670d\u52a1\u5668\u53ef\u6309 Ctrl+C \u7ed3\u675f。
powershell -NoProfile -Command "try { $r=Invoke-RestMethod 'http://localhost:8765/api/health' -TimeoutSec 2; if($r.project -eq 'ECE191-MTR'){exit 0}; exit 1 } catch { exit 1 }"
if not errorlevel 1 (
  start "" "http://localhost:8765"
  exit /b 0
)
start "" "http://localhost:8765"
wsl -d Ubuntu -- bash -lc "cd historical-project && bash run_wsl.sh project_demo.py --port 8765"
pause
