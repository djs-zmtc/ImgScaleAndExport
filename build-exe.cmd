@echo off
rem Builds dist\ImgScaleAndExport.exe with PyInstaller (run from anywhere).
pushd "%~dp0"
uv run --group build pyinstaller --noconfirm --distpath dist --workpath build packaging/ImgScaleAndExport.spec
set RC=%ERRORLEVEL%
popd
if %RC%==0 echo Built: %~dp0dist\ImgScaleAndExport.exe
exit /b %RC%
