"""Push the Python LOP sources into assets.hip's /stage nodes.

In Houdini's Python Shell:
    exec(open(hou.expandString('$HIP/scripts/apply_lookdev_lops.py')).read())
or headless: hython scripts/apply_lookdev_lops.py  (loads + saves assets.hip)
"""
import os
import hou

NODES = {
    "/stage/shaderball_grid": "lop_shaderball_grid.py",
}


def apply():
    here = hou.expandString("$HIP/scripts")
    for path, fname in NODES.items():
        node = hou.node(path)
        if node is None:
            print("missing node", path)
            continue
        with open(os.path.join(here, fname), encoding="utf-8") as f:
            node.parm("python").set(f.read())
        print("updated", path)


if hou.isUIAvailable():
    apply()
elif __name__ == "__main__":
    hip = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets.hip")
    hou.hipFile.load(hip.replace("\\", "/"), suppress_save_prompt=True, ignore_load_warnings=True)
    apply()
    hou.hipFile.save()
