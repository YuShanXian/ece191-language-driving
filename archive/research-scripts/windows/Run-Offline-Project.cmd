@echo off
chcp 65001 >nul
echo ECE191 \u5b8c\u6574\u79bb\u7ebf\u6d41\u7a0b：\u6570\u636e、\u73af\u5883、\u7f13\u5b58\u6a21\u578b\u6d41\u6c34\u7ebf、\u8bc4\u4ef7\u548c\u62a5\u544a。
echo \u9ed8\u8ba4\u4e0d\u542f\u52a8\u7f3a\u5c11\u7684\u6a21\u578b\u8ba1\u7b97；\u6240\u6709\u8bb0\u5f55\u4fdd\u5b58\u5728 baseline-v1/workflows/。
wsl -d Ubuntu -- bash -lc "cd historical-project && bash run_wsl.sh run_offline_project.py --tag baseline-v1"
set "workflow_exit=%errorlevel%"
if not "%workflow_exit%"=="0" echo \u6d41\u7a0b\u672a\u5b8c\u6210，\u8bf7\u67e5\u770b\u4e0a\u65b9\u65e5\u5fd7。
if "%workflow_exit%"=="0" echo \u62a5\u544a：historical-project\runs\project-v2\baseline-v1\report\index.html
pause
exit /b %workflow_exit%
