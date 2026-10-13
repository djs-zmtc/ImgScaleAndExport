@echo off
rem Wrapper for ImgScaleAndExport: runs the CLI via uv from any directory.
rem --project points at this script's folder; the caller's working directory
rem is preserved so relative image paths keep working. All args pass through.
uv run --project "%~dp0." imgscaleandexport %*
exit /b %ERRORLEVEL%
