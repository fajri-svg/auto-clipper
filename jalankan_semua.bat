@echo off
echo ========================================
echo   Auto Clipper - Jalankan Semua v4
echo   (n8n Windows - Tanpa Docker!)
echo ========================================
echo.

echo [1/2] Menjalankan Clipper Server...
start "Clipper Server" cmd /k "python D:\Tools\n8n_scripts\clipper_server.py"

echo [2/2] Menjalankan n8n...
start "n8n" cmd /k "n8n start"

echo.
echo ========================================
echo  Tunggu 20 detik lalu buka:
echo    n8n    : http://localhost:5678
echo    Health : http://localhost:5680/health
echo ========================================
echo.
pause