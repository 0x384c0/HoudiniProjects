@echo off
setlocal enabledelayedexpansion

set "python_script=..\GI-Model-Importer\Tools\genshin_3dmigoto_collect.py"

for /f %%i in (input.txt) do (
    set "vb_id=%%i"
    python "%python_script%" -vb !vb_id! -n !vb_id!
)

endlocal

pause