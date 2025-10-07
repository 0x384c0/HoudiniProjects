"""Build hda/matgen_mtlx.hda (LOP: MaterialX Texture Material Generator).

    hython scripts/build_matgen_hda.py

Embeds scripts/matgen_mtlx.py as the HDA's PythonModule. Edit that file and rerun.
"""

import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
W3 = os.path.dirname(HERE)
HDA_FILE = os.path.join(W3, "hda", "matgen_mtlx.hda").replace("\\", "/")
TYPE_NAME = "matgen_mtlx"
LABEL = "MaterialX Texture Material Generator"

sys.path.insert(0, HERE)
import matgen_mtlx as mg  # noqa: E402

CS_MENU = ["", "Auto (file rules)", "Raw", "Raw", "sRGB - Texture", "sRGB - Texture",
           "ACEScg", "ACEScg", "Linear Rec.709 (sRGB)", "Linear Rec.709 (sRGB)",
           "ACES2065-1", "ACES2065-1"]


def cb(fn):
    return "hou.phm().%s(kwargs['node'])" % fn


def parm_group():
    g = hou.ParmTemplateGroup()

    g.append(hou.ButtonParmTemplate(
        "rescan", "Rescan Folder", script_callback=cb("rescan"),
        script_callback_language=hou.scriptLanguage.Python,
        help="The node is stateless and rescans automatically when parameters or the "
             "folder change. Press to force a rescan and refresh the report."))

    src = hou.FolderParmTemplate("f_source", "Source", folder_type=hou.folderType.Simple)
    src.addParmTemplate(hou.StringParmTemplate(
        "texdir", "Texture Directory", 1,
        default_value=("$HIP_CACHE/TMP/assets/cruiser/text/_publish/v003/2k",),
        string_type=hou.stringParmType.FileReference, file_type=hou.fileType.Directory,
        help="Folder with the texture set. Variables ($HIP_CACHE, $HIP...) are kept "
             "unexpanded in the generated image nodes."))
    src.addParmTemplate(hou.ToggleParmTemplate("recursive", "Include Subfolders", False))
    src.addParmTemplate(hou.StringParmTemplate(
        "extensions", "Extensions", 1, default_value=("exr tx tif tiff png jpg jpeg",),
        help="Space separated. If one channel exists in several formats, the earlier "
             "extension wins."))
    g.append(src)

    nm = hou.FolderParmTemplate("f_naming", "Naming", folder_type=hou.folderType.Simple)
    nm.addParmTemplate(hou.ToggleParmTemplate(
        "strip_common", "Strip Common Prefix", True,
        help="Remove the prefix shared by all material names "
             "(cruiser_mdl_v030_ship -> ship)."))
    nm.addParmTemplate(hou.StringParmTemplate("name_prefix", "Material Name Prefix", 1))
    nm.addParmTemplate(hou.StringParmTemplate(
        "custom_regex", "Custom File Regex", 1,
        help="Optional. Python regex searched in the file name (no extension/UDIM) with "
             "named groups (?P<material>...) and (?P<channel>...). The channel text is then "
             "matched against the channel patterns below. Leave empty for token detection: "
             "the LAST channel token found in the name is the channel, everything before "
             "it is the material, anything after it (colorspace suffix etc.) is ignored."))

    mp = hou.FolderParmTemplate("channels", "Channel Patterns",
                                folder_type=hou.folderType.MultiparmBlock,
                                default_value=0)
    mp.addParmTemplate(hou.ToggleParmTemplate("ch_enable#", "", True, join_with_next=True))
    mp.addParmTemplate(hou.StringParmTemplate(
        "ch_target#", "Channel", 1, default_value=("basecolor",),
        menu_items=mg.CHANNEL_KEYS,
        menu_labels=[mg.CHANNEL_DEFS[k]["label"] for k in mg.CHANNEL_KEYS],
        menu_type=hou.menuType.Normal, join_with_next=True))
    mp.addParmTemplate(hou.StringParmTemplate(
        "ch_colorspace#", "Colorspace", 1, menu_items=CS_MENU[0::2],
        menu_labels=CS_MENU[1::2], menu_type=hou.menuType.StringReplace))
    mp.addParmTemplate(hou.StringParmTemplate(
        "ch_tokens#", "Tokens (regex)", 1,
        help="Regex alternatives, case-insensitive, matched as a whole token "
             "(not touching letters/digits), e.g. basecolor|albedo|diffuse."))
    nm.addParmTemplate(mp)
    nm.addParmTemplate(hou.ButtonParmTemplate(
        "reset_patterns", "Reset Patterns", script_callback=cb("reset_patterns"),
        script_callback_language=hou.scriptLanguage.Python))
    g.append(nm)

    out = hou.FolderParmTemplate("f_output", "Output", folder_type=hou.folderType.Simple)
    out.addParmTemplate(hou.StringParmTemplate("matprefix", "Material Path Prefix", 1,
                                               default_value=("/materials/",)))
    out.addParmTemplate(hou.StringParmTemplate(
        "height_mode", "Height as", 1, default_value=("displacement",),
        menu_items=("displacement", "bump", "off"),
        menu_labels=("Displacement", "Bump", "Off"),
        help="Displacement: height map -> displacement output (needs subdividable meshes in "
             "Arnold). Bump: same height (same height_scale) as a bump on top of the normal "
             "map; renders alike in Karma and Arnold, no tessellation. Off: ignore height."))
    out.addParmTemplate(hou.ToggleParmTemplate(
        "fill_udims", "Fill Missing UDIM Tiles", True,
        help="If a channel lacks tiles that other channels of the same material have (e.g. "
             "emissive only on some tiles), build a complete tile set in the Fill Directory: "
             "hard links to the real tiles + 4x4 neutral placeholders. Arnold GPU renders "
             "shaders that hit a missing tile red; Karma/Arnold CPU treat them as empty."))
    out.addParmTemplate(hou.StringParmTemplate(
        "filldir", "Fill Directory", 1, default_value=("$HIP_CACHE/matgen_udimfill",),
        string_type=hou.stringParmType.FileReference, file_type=hou.fileType.Directory,
        disable_when="{ fill_udims == 0 }"))
    g.append(out)

    rep = hou.StringParmTemplate("report", "Report", 1, tags={"editor": "1",
                                                              "editorlines": "8-30"})
    g.append(rep)
    return g


def build():
    stage = hou.node("/stage")
    old = stage.node(TYPE_NAME + "_build")
    if old:
        old.destroy()
    sub = stage.createNode("subnet", TYPE_NAME + "_build")
    for c in sub.children():
        if c.type().name() != "output":
            c.destroy()
    out = sub.node("output0")

    hda_expr = "hou.node('..')"
    empty = sub.createNode("sublayer", "empty")          # loop body starts from nothing
    begin = sub.createNode("begincontextoptionsblock", "begin")
    begin.setInput(0, empty)
    lib = sub.createNode("materiallibrary", "materials")
    lib.setInput(0, begin)
    lib.parm("matnode1").set("template")
    lib.parm("matpath1").setExpression(
        "%s.evalParm('matprefix').rstrip('/') + '/' + "
        "(hou.contextOption('ITERATIONVALUE') or 'template')" % hda_expr,
        hou.exprLanguage.Python)
    mg.build_template(lib, "template")
    prune = sub.createNode("pythonscript", "prune")
    prune.setInput(0, lib)
    prune.parm("python").set(chr(10).join([
        "node = hou.pwd()",
        "hda = node.parent()",
        "hda.hdaModule().prune_material(hda, node.editableStage())",
    ]))
    loop = sub.createNode("foreach", "foreach")
    loop.setInput(0, sub.indirectInputs()[0])            # result merged onto the HDA input
    loop.setInput(2, prune)
    loop.parm("itermethod").set("strings")
    loop.parm("strings").setExpression(
        "%s.hdaModule().material_names(%s)" % (hda_expr, hda_expr), hou.exprLanguage.Python)
    out.setInput(0, loop)
    sub.layoutChildren()

    os.makedirs(os.path.dirname(HDA_FILE), exist_ok=True)
    hda = sub.createDigitalAsset(name=TYPE_NAME, hda_file_name=HDA_FILE, description=LABEL,
                                 min_num_inputs=0, max_num_inputs=1, version="1.0",
                                 ignore_external_references=True, create_backup=False)
    d = hda.type().definition()
    d.setParmTemplateGroup(parm_group())
    d.addSection("PythonModule", open(os.path.join(HERE, "matgen_mtlx.py"),
                                      encoding="utf-8").read())
    d.setExtraFileOption("PythonModule/IsPython", True)
    d.addSection("OnCreated", "kwargs['node'].hdaModule().on_created(kwargs['node'])\n")
    d.setExtraFileOption("OnCreated/IsPython", True)
    d.setIcon("VOP_mtlxstandard_surface")
    d.addSection("Tools.shelf", """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="network"><contextOpType>$HDA_TABLE_AND_NAME</contextOpType></toolMenuContext>
    <toolSubmenu>Material</toolSubmenu>
    <script scriptType="python"><![CDATA[import loptoolutils
loptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
""")
    d.save(HDA_FILE, hda, d.options())
    hda.destroy()
    print("wrote", HDA_FILE)


if __name__ == "__main__":
    build()
