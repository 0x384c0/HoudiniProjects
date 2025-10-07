"""Fill a Component Material LOP's assignment rows from a material-name attribute.

One row per unique value of a primitive string attribute (default ``mtl``) on the SOP
geometry that feeds Component Geometry. The SOP network groups render meshes under one
scope per material (path = /<mtl>/<part>), so each row binds a whole scope:
    /ASSET/geo/render/<mtl>  ->  /ASSET/mtl/<mtl>

Run after the material set changes (Houdini Python Shell):
    exec(open(hou.text.expandString('$HIP/scripts/assign_component_materials.py')).read())
    assign()
"""

import hou

DEFAULTS = dict(
    cm="/stage/componentmaterial1",
    sop="/stage/componentgeometry1/sopnet/geo/RENDER",
    attr="mtl",
    geo_root="/ASSET/geo/render",
    mtl_root="/ASSET/mtl",
)


def _multiparm(node):
    for pt in node.parmTemplateGroup().entries():
        stack = [pt]
        while stack:
            t = stack.pop()
            if isinstance(t, hou.FolderParmTemplate):
                if t.folderType() in (hou.folderType.MultiparmBlock,
                                      hou.folderType.ScrollingMultiparmBlock,
                                      hou.folderType.TabbedMultiparmBlock):
                    if any(c.name() == "primpattern#" for c in t.parmTemplates()):
                        return node.parm(t.name())
                stack.extend(t.parmTemplates())
    raise hou.Error("No material assignment multiparm on %s" % node.path())


def assign(cm=None, sop=None, attr=None, geo_root=None, mtl_root=None):
    o = dict(DEFAULTS)
    o.update({k: v for k, v in dict(cm=cm, sop=sop, attr=attr, geo_root=geo_root,
                                    mtl_root=mtl_root).items() if v})
    cm_node, sop_node = hou.node(o["cm"]), hou.node(o["sop"])
    geo = sop_node.geometry()
    a = geo.findPrimAttrib(o["attr"])
    if a is None:
        raise hou.Error("%s has no prim attribute '%s'" % (sop_node.path(), o["attr"]))
    names = sorted(n for n in a.strings() if n)
    mp = _multiparm(cm_node)
    mp.set(0)
    mp.set(len(names))
    for i, n in enumerate(names, 1):
        cm_node.parm("enable%d" % i).set(1)
        cm_node.parm("primpattern%d" % i).set("%s/%s" % (o["geo_root"], n))
        cm_node.parm("matspecpath%d" % i).set("%s/%s" % (o["mtl_root"], n))
    print("assigned %d materials: %s" % (len(names), " ".join(names)))
    return names
