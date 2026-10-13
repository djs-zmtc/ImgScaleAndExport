# Wrapper for ImgScaleAndExport: runs the CLI via uv from any directory.
# --project points at this script's folder; the caller's working directory is
# preserved so relative image paths keep working. All arguments pass through.
uv run --project $PSScriptRoot imgscaleandexport @args
exit $LASTEXITCODE
