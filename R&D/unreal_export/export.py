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

def get_subpath(object_path):
    return os.path.relpath(os.path.dirname(object_path), '/Game')

def convert_material_path_to_filename(input_path, parameter_name):
    names_map = {
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
    nanite_settings = static_mesh.get_editor_property("nanite_settings")
    if (nanite_settings.enabled):
        print(f"Disabling nanite for {static_mesh}")
        nanite_settings.enabled = False
        static_mesh_editor_subsystem.set_nanite_settings(static_mesh, nanite_settings)

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
        print(f"Exported to {output_file}")

    elif type(asset_object) is unreal.MaterialInstanceConstant:
        print(f"Exporting MaterialInstanceConstant {object_path}")

        export_material_textures(asset_object, object_path, output_path)
        print(f"Exported")

    else:
        warnings.warn(f'Unsupported type {type(asset_object)} for asset "{object_path}"')

def get_sort_key_material(object_path):
    asset_info = asset_registry.get_asset_by_object_path(object_path)
    asset_object = asset_info.get_asset()
    return 1 if type(asset_object) is unreal.MaterialInstanceConstant else 0

output_path = "D:/3D Objects/Unreal Projects/export"

path = unreal.EditorUtilityLibrary.get_current_content_browser_path()
asset_data_list = unreal.EditorAssetLibrary.list_assets(path, recursive=True)
asset_data_list.sort(get_sort_key_material)
for object_path in asset_data_list:
    export_object(object_path, output_path)

print("!!!!!! Done !!!!!!!")