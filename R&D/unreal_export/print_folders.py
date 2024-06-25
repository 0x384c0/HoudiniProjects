import os
import unreal

def main():
    path = unreal.EditorUtilityLibrary.get_current_content_browser_path()
    subfolders = unreal.EditorAssetLibrary.list_assets(path, False, True)

    for subfolder in subfolders:
        print(subfolder)

main()