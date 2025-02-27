@echo off

set UnrealEditor="D:\Program Files\Epic Games\UE_5.5\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
set ProjectPath="D:\3D Objects\Unreal Projects\ValleyoftheAncient\ValleyoftheAncient.uproject"
set ExportScript="%cd%\export.py"

@REM Exporting by small batches due memoy leak in unreal
@REM OUTPUT_PATH and ASSETS_PATH are vairables for export.py
set OUTPUT_PATH=F:/houdini_cache/ancient_valley_export

set ASSETS_PATH=/Game/AncientContent/Geometry/Buttes/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/ErosionGround/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/GroundTiles/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/MASS/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/PedestalRock/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/PillarCollection/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/SpireRockCollection/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/StoneBlock/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

set ASSETS_PATH=/Game/AncientContent/Geometry/Surfaces/
%UnrealEditor% %ProjectPath% -nosplash -Unattended -nopause -nocontentbrowser -log -RenderOffscreen -ExecutePythonScript=%ExportScript%

