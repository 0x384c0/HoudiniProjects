# unreal 5.6 
import unreal

# Configurable variables
ASSETS_PATH = '/Game/Fab'
SPACING = 30
COLS = 5

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

def get_static_mesh_bounds(static_mesh):
    # Get the bounding box extent (half size) of the mesh
    bounding_box = static_mesh.get_bounding_box()
    min_vec = bounding_box.min
    max_vec = bounding_box.max
    size_x = max_vec.x - min_vec.x
    return size_x

def place_object(object_path, index, prev_end_x=0):
    asset_info = asset_registry.get_asset_by_object_path(object_path)
    asset_object = asset_info.get_asset()

    if type(asset_object) is unreal.StaticMesh:
        mesh_size_x = get_static_mesh_bounds(asset_object)
        # Place at the end of previous mesh, with spacing
        location_x = prev_end_x + (mesh_size_x / 2.0)
        location = unreal.Vector(location_x, 0, 0)
        print(f"Spawning {asset_object.get_name()} at {location}.")
        actor = unreal.EditorLevelLibrary.spawn_actor_from_object(asset_object, location)
        if actor:
            actor.set_folder_path('Assets')
        # Return the new end x for next mesh
        return location_x + (mesh_size_x / 2.0) + SPACING
    return prev_end_x

def is_static_mesh(asset_object):
    return type(asset_object) is unreal.StaticMesh

def remove_actors():
    # Remove all actors in the 'Assets' folder
    all_actors = unreal.EditorLevelLibrary.get_all_level_actors()
    for actor in all_actors:
        if actor.get_folder_path() == 'Assets':
            unreal.EditorLevelLibrary.destroy_actor(actor)


def main():
    print("------ Start ------")
    print(f"Searching for StaticMesh assets in {ASSETS_PATH}...")
    asset_data_list = unreal.EditorAssetLibrary.list_assets(ASSETS_PATH, recursive=True)

    print(f"Found {len(asset_data_list)} objects.")

    # Get the currently opened level path
    editor_world = unreal.EditorLevelLibrary.get_editor_world()
    current_level_path = editor_world.get_path_name()
    print(f"Current opened level: {current_level_path}")

    print("Remove actors")
    remove_actors()

    prev_end_x = 0
    for i, object_path in enumerate(asset_data_list):
        prev_end_x = place_object(object_path, i, prev_end_x)

    print("------ Done ------")

main()