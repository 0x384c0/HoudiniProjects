@REM ref. https://www.sidefx.com/docs/houdini/tops/cooking.html#cookcommandline

@REM User Settings
SET "houdiniVersion=20.5.278"
SET "hipFile=shogun.hip"
@REM %ProgramFiles%
SET "houdiniProgramFiles=F:/Program Files" 

@REM Set Houdini path
SET "houdiniPath=%houdiniProgramFiles%/Side Effects Software/Houdini %houdiniVersion%/"
SET "hbatchDir=%houdiniPath%bin/"

@REM Hexpand

mkdir tmp
cd tmp
"%hbatchDir%hcpio.exe" -idI ../%hipFile%
pause