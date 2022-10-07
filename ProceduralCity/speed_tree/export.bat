set app_location="E:\Applications\Installed\ART\SpeedTree\SpeedTree Cinema v8.4.2\win64\SpeedTree Modeler Cinema.com"

if not exist "export\" mkdir "export\"
%app_location% "GrassVar1.spm" -export "export\GrassVar1.fbx" -export_options "export_options.ini"
%app_location% "TreeVar1.spm" -export "export\TreeVar1.fbx" -export_options "export_options.ini"
%app_location% "TreeVar2.spm" -export "export\TreeVar2.fbx" -export_options "export_options.ini"
%app_location% "TreeVar3.spm" -export "export\TreeVar3.fbx" -export_options "export_options.ini"
%app_location% "TreeVar4.spm" -export "export\TreeVar4.fbx" -export_options "export_options.ini"
pause