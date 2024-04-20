import os
import warnings
import unreal

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
static_mesh_editor_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

def export_usd_mesh(static_mesh, output_file):
    task = unreal.AssetExportTask()
    task.object = static_mesh
    task.filename = output_file
    task.selected = True
    task.replace_identical = True
    task.prompt = False
    task.automated = True
    task.options = unreal.StaticMeshExporterUSDOptions()
    task.options.stage_options = unreal.UsdStageOptions()
    task.options.stage_options.up_axis = unreal.UsdUpAxis.Y_AXIS
    task.options.mesh_asset_options = unreal.UsdMeshAssetOptions()
    task.options.mesh_asset_options.bake_materials = True
    task.options.mesh_asset_options.lowest_mesh_lod = 0
    task.options.mesh_asset_options.material_baking_options = unreal.UsdMaterialBakingOptions()
    task.options.mesh_asset_options.material_baking_options.constant_color_as_single_value = True
    task.options.mesh_asset_options.material_baking_options.default_texture_size = unreal.IntPoint(4096, 4096)
    task.options.mesh_asset_options.material_baking_options.textures_dir = unreal.DirectoryPath(os.path.join(os.path.dirname(output_file), "Textures"))
    unreal.Exporter.run_asset_export_task(task)

def export_png(texture_2d, output_file):
    texture_exporter = unreal.TextureExporterPNG()
    task = unreal.AssetExportTask()
    task.object = texture_2d
    task.filename = output_file
    task.exporter = texture_exporter
    task.automated = True
    task.prompt = False
    task.replace_identical = True
    unreal.Exporter.run_asset_export_task(task)

def export_usd_material(material_instance_constant, output_file):
    task = unreal.AssetExportTask()
    task.object = material_instance_constant
    task.filename = output_file
    task.automated = True
    task.replace_identical = True
    task.exporter = unreal.MaterialExporterUsd()
    task.options = unreal.MaterialExporterUSDOptions()
    task.options.material_baking_options = unreal.UsdMaterialBakingOptions()
    task.options.material_baking_options.default_texture_size = unreal.IntPoint(4096, 4096)
    task.options.material_baking_options.textures_dir = unreal.DirectoryPath(os.path.join(os.path.dirname(output_file), "Textures"))
    result = unreal.Exporter.run_asset_export_task(task)

def disable_nanite(static_mesh):
    nanite_settings = static_mesh.get_editor_property("nanite_settings")
    if (nanite_settings.enabled):
        print(f"Disabling nanite for {static_mesh}")
        nanite_settings.enabled = False
        static_mesh_editor_subsystem.set_nanite_settings(static_mesh, nanite_settings)

def cread_dirs(output_file):
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

def get_subpath(object_path):
    return os.path.relpath(os.path.dirname(object_path), '/Game')

def export_object(object_path, output_path):
    asset_info = asset_registry.get_asset_by_object_path(object_path)
    asset_object = asset_info.get_asset()

    if (type(asset_object) is unreal.StaticMesh):
        print(f"Exporting StaticMesh {object_path}")
        disable_nanite(asset_object)
        
        output_file = os.path.join(output_path, get_subpath(object_path), f"{asset_info.asset_name}.usd")
        cread_dirs(output_file)

        export_usd_mesh(asset_object, output_file)
        print(f"Exported to {output_file}")

    elif (type(asset_object) is unreal.MaterialInstanceConstant):
        print(f"Exporting MaterialInstanceConstant {object_path}")
        
        output_file = os.path.join(output_path, get_subpath(object_path), f"{asset_info.asset_name}.usd")
        cread_dirs(output_file)

        export_usd_material(asset_object, output_file)
        print(f"Exported to {output_file}")

    elif (type(asset_object) is unreal.Texture2D):
        print(f"Exporting Texture2D {object_path}")
        
        output_file = os.path.join(output_path, get_subpath(object_path), f"{asset_info.asset_name}.png")
        cread_dirs(output_file)

        export_png(asset_object, output_file)
        print(f"Exported to {output_file}")

    else:
        warnings.warn(f'Unsupported type {type(asset_object)} for asset "{object_path}"')


output_path = "D:/3D Objects/Unreal Projects/export"

path = unreal.EditorUtilityLibrary.get_current_content_browser_path()
asset_data_list = unreal.EditorAssetLibrary.list_assets(path, recursive=True)
for object_path in asset_data_list:
    export_object(object_path, output_path)