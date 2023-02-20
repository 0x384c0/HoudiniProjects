@REM ref. https://www.sidefx.com/docs/houdini/tops/cooking.html#cookcommandline

@REM User Settings
SET "houdiniVersion=19.0.383"
SET "hipFile=JetExplosion.hip"
SET "topPath=/tasks/topnet1/output0"
@REM %ProgramFiles%
SET "houdiniProgramFiles=D:/Program Files" 

@REM Set Houdini path
SET "houdiniPath=%houdiniProgramFiles%/Side Effects Software/Houdini %houdiniVersion%/"
SET "hbatchDir=%houdiniPath%bin/"
SET "hhp=%houdiniPath%houdini/python3.7libs/"

@REM Cook Tops
"%hbatchDir%hython.exe" "%hhp%pdgjob/topcook.py" --hip "%~dp0%hipFile%" --toppath %topPath%
shutdown -s -t 120
@rem Press any button to abort shutdown
pause
shutdown -a