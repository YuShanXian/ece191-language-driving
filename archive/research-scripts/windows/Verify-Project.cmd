@echo off
chcp 65001 >nul
echo ECE191 \u672c\u673a\u9879\u76ee\u9a8c\u8bc1：\u68c0\u67e5\u7a0b\u5e8f、\u73af\u5883、\u5df2\u4fdd\u5b58\u6570\u636e，\u5e76\u91cd\u5efa\u62a5\u544a。
echo \u4e0d\u91cd\u65b0\u8bad\u7ec3\u6216\u8fd0\u884c MTR \u63a8\u7406。\u65e5\u5fd7\u4fdd\u5b58\u5728 runs/project-v2/verification/。
wsl -d Ubuntu -- bash -lc "cd historical-project && bash run_wsl.sh reproduce_project.py --environment --refresh-reports"
set "verification_exit=%errorlevel%"
if not "%verification_exit%"=="0" echo \u9a8c\u8bc1\u672a\u901a\u8fc7，\u8bf7\u67e5\u770b\u4e0a\u65b9\u65e5\u5fd7\u8def\u5f84。
pause
exit /b %verification_exit%
