import os
import warnings
import unreal

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
static_mesh_editor_subsystem = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

def export_usd_mesh(static_mesh, output_file):
    task = unreal.AssetExportTask()
    task.object = static_mesh
    task.filename = output_file
    task.replace_identical = True
    task.prompt = False
    task.automated = True
    task.options = unreal.StaticMeshExporterUSDOptions()
    task.options.stage_options = unreal.UsdStageOptions()
    task.options.stage_options.up_axis = unreal.UsdUpAxis.Y_AXIS
    task.options.stage_options.meters_per_unit = 1
    task.options.mesh_asset_options = unreal.UsdMeshAssetOptions()
    task.options.mesh_asset_options.bake_materials = True
    task.options.mesh_asset_options.lowest_mesh_lod = 0
    task.options.mesh_asset_options.material_baking_options = unreal.UsdMaterialBakingOptions()
    task.options.mesh_asset_options.material_baking_options.constant_color_as_single_value = True
    task.options.mesh_asset_options.material_baking_options.default_texture_size = unreal.IntPoint(64, 64)
    task.options.mesh_asset_options.material_baking_options.textures_dir = unreal.DirectoryPath(os.path.join(os.path.dirname(output_file), "Textures"))
    unreal.Exporter.run_asset_export_task(task)

def export_usd_material(material_instance, output_file, only_textures = False):
    iterations = 10
    for i in range(iterations): # Run export task multiple times to fix texture quality. This issue probably related to Texture Streaming.
        task = unreal.AssetExportTask()
        task.object = material_instance
        task.filename = output_file
        task.replace_identical = True
        task.prompt = False
        task.automated = True
        task.options = unreal.MaterialExporterUSDOptions()
        task.options.material_baking_options = unreal.UsdMaterialBakingOptions()
        task.options.material_baking_options.constant_color_as_single_value = True
        task.options.material_baking_options.default_texture_size = unreal.IntPoint(4096, 4096)
        task.options.material_baking_options.textures_dir = unreal.DirectoryPath(os.path.join(os.path.dirname(output_file), "Textures"))
        if i != (iterations - 1): # write textures only at last iteration
            task.options.material_baking_options.textures_dir.path = os.path.join(task.options.material_baking_options.textures_dir.path, os.devnull)

        unreal.Exporter.run_asset_export_task(task)
    if only_textures:
        os.remove(output_file)

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

def get_subpath(object_path):
    return os.path.relpath(os.path.dirname(object_path), '/Game')

def convert_material_path_to_filename(input_path, parameter_name):
    names_map = {
        "BaseColor": "BaseColor",
        "Albedo": "BaseColor",
        "Roughness": "Roughness",
        "Normal": "Normal",
    }
    name_key = str(parameter_name)
    if name_key not in names_map:
        return None
    name = names_map[name_key]
    result = input_path[1:] # remove first character
    result = ".".join(result.split(".")[:1]) # remove last 
    result = result.replace("/", "_")
    result += f"_{name}"
    return result

def export_material_textures(asset_object, object_path, output_path):
    for texture_parameter_value in asset_object.texture_parameter_values:
        texture_filename = convert_material_path_to_filename(asset_object.get_path_name(), texture_parameter_value.parameter_info.name)
        if texture_filename is None:
            continue
        texture_2d = texture_parameter_value.parameter_value;
        output_file = os.path.join(output_path, get_subpath(object_path), "Textures", f"{texture_filename}.png")

        export_png(texture_2d, output_file)

def disable_nanite(static_mesh):
    """
    used to export original mesh as USD https://forums.unrealengine.com/t/fast-method-of-exporting-level-meshes-and-nanite/1691893/3
    will cause memory leak for each call
    """
    nanite_settings = static_mesh.get_editor_property("nanite_settings")
    if (nanite_settings.enabled):
        print(f"Disabling nanite for {static_mesh}")
        nanite_settings.enabled = False
        static_mesh_editor_subsystem.set_nanite_settings(static_mesh, nanite_settings)

def undo_changes():
    dirty_content_packages = unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
    unreal.EditorLoadingAndSavingUtils.reload_packages(dirty_content_packages, interaction_mode=unreal.ReloadPackagesInteractionMode.ASSUME_POSITIVE)

def cread_dirs(output_file):
    output_dir = os.path.dirname(output_file)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

def export_object(object_path, output_path):
    asset_info = asset_registry.get_asset_by_object_path(object_path)
    asset_object = asset_info.get_asset()

    if type(asset_object) is unreal.StaticMesh:
        print(f"Exporting StaticMesh {object_path}")
        disable_nanite(asset_object)
        
        output_file = os.path.join(output_path, get_subpath(object_path), f"{asset_info.asset_name}.usd")
        cread_dirs(output_file)

        export_usd_mesh(asset_object, output_file)

        material = asset_object.get_material(0)
        output_file = os.path.join(output_path, get_subpath(object_path), f"{asset_info.asset_name}_Material.usd")
        export_usd_material(material, output_file, True)
        export_material_textures(material, object_path, output_path)

        print(f"Exported to {output_file}")

def get_sort_key_material(object_path):
    asset_info = asset_registry.get_asset_by_object_path(object_path)
    asset_object = asset_info.get_asset()
    return 1 if type(asset_object) is unreal.MaterialInstanceConstant else 0


def main():
    print("------ Start Exporting ------")

    output_path = os.environ.get('OUTPUT_PATH', "F:/houdini_cache/ancient_valley_export")
    
    path = os.environ.get('ASSETS_PATH', unreal.EditorUtilityLibrary.get_current_content_browser_path())
    
    if path is None or output_path is None:
        print("Empty paths. Aborting")
        return
    else:
        print("Exporting from path: " + path)

    asset_data_list = unreal.EditorAssetLibrary.list_assets(path, recursive=True)
    asset_data_list.sort(get_sort_key_material)
    for object_path in asset_data_list:
        export_object(object_path, output_path)

    print("------ Done Exporting ------")

main()