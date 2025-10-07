"""MaterialX texture-set material generator (PythonModule of the matgen_mtlx LOP HDA).

Stateless: the node stores nothing in the .hip; its output depends only on its parameters
(and the files on disk). Cache the result downstream with a File Cache LOP.

Inside the HDA (locked contents, built by build_matgen_hda.py):
  begin (Begin Context Options Block) -> materials (Material Library holding ONE template
  MaterialX Standard Surface: every channel branch, range/hsvadjust/normalmap/displacement,
  UV transform, promoted Parameter VOPs = USD Material inputs) -> prune (Python LOP)
  -> foreach (For Each over material_names(), iteration value = material name).
  * material path, image files and colorspaces are expressions reading the iteration value;
  * prune removes the branches of channels the current texture set doesn't have.

Python (this module): scan the texture folder, parse file names into (material, channel)
with editable regex patterns, collapse UDIM tiles to <UDIM>, optionally fill missing UDIM
tiles. Scans are cached per parameter values + folder mtime.

Template naming contract: every node of a channel branch is named ``<channel>_*`` and the
texture reader is ``<channel>_image``; prune removes prims/inputs with that prefix.

Embedded into the HDA by build_matgen_hda.py; edit here and rebuild.
"""

import os
import re

import hou

# ---------------------------------------------------------------------------------------
# Channel definitions (template branches)
# ---------------------------------------------------------------------------------------
# kind: color  -> image(color3) > range(color3) [> hsvadjust] > surface input
#       float  -> image(float)  > range(float) > surface input
#       normal -> image(vector3) > normalmap(scale) > surface.normal
#       height -> image(float) > range(float) > displacement(scale) > displacement output
CHANNELS = [
    ("basecolor", dict(label="Base Color", kind="color", target="base_color", hsv=True)),
    ("metalness", dict(label="Metalness", kind="float", target="metalness")),
    ("roughness", dict(label="Specular Roughness", kind="float", target="specular_roughness")),
    ("specular", dict(label="Specular Weight", kind="float", target="specular")),
    ("emission", dict(label="Emission Color", kind="color", target="emission_color", hsv=True)),
    ("opacity", dict(label="Opacity", kind="color", target="opacity", hsv=False)),
    ("normal", dict(label="Normal", kind="normal", target="normal")),
    ("height", dict(label="Height (Displacement)", kind="height", target="displacement")),
]
CHANNEL_KEYS = [k for k, _ in CHANNELS]
CHANNEL_DEFS = dict(CHANNELS)

# Default detection patterns: (channel, regex alternatives, colorspace, enabled).
# Matched case-insensitively as a whole token (not touching letters/digits) in the file
# name without extension and UDIM. Colorspace "" = auto (OCIO file rules in Karma; Arnold:
# 8-bit -> sRGB, float -> scene linear). Data maps are forced to Raw so 8-bit PNG/JPG
# normal/roughness maps are not sRGB-decoded by Arnold.
DEFAULT_PATTERNS = [
    ("basecolor", "basecolor|base_color|albedo|diffuse|diff|color|col", "", 1),
    ("metalness", "metallic|metalness|metal", "Raw", 1),
    ("roughness", "roughness|rough", "Raw", 1),
    ("specular", "specular|spec", "Raw", 1),
    ("emission", "emissive|emission|emit|glow", "", 1),
    ("opacity", "opacity|alpha|transparency", "Raw", 1),
    ("normal", "normalgl|normal_opengl|normal|nrm|nor", "Raw", 1),
    ("height", "height|displacement|disp", "Raw", 1),
]

UDIM_RE = re.compile(r"(?<=[._])(1\d{3})$")
SEPS = "_.- "

# ---------------------------------------------------------------------------------------
# Template network
# ---------------------------------------------------------------------------------------

def _setup_mtlx_subnet(sub):
    """Turn a VOP subnet into a MaterialX builder material (same as the tab tool)."""
    import voptoolutils
    voptoolutils._setupMtlXBuilderSubnet(subnet_node=sub, name=sub.name())
    sub.setMaterialFlag(True)


def _connector(sub, name, label, parmtype, src):
    c = sub.createNode("subnetconnector", name + "_output")
    c.parm("connectorkind").set("output")
    c.parm("parmname").set(name)
    c.parm("parmlabel").set(label)
    c.parm("parmtype").set(parmtype)
    if src is not None:
        c.setInput(0, src)
    return c


def _promote(node, input_name, parm_name, label):
    """Parameter VOP on an input -> USD Material input (default = the input's current value)."""
    node.insertParmGenerator(input_name, hou.vopParmGenType.Parameter, False)
    p = node.input(node.inputIndex(input_name))
    p.setName(parm_name, unique_name=True)
    p.parm("parmname").set(parm_name)
    p.parm("parmlabel").set(label)
    return p


def _range(sub, ch, label, sig, src, defaults=None):
    r = sub.createNode("mtlxrange", ch + "_range")
    r.parm("signature").set(sig)
    r.setInput(0, src)
    for inp, val in (defaults or {}).items():
        if sig == "color3":
            r.parmTuple(inp + "_color3").set((val, val, val))
        else:
            r.parm(inp).set(val)
    for inp, lab in (("inlow", "In Low"), ("inhigh", "In High"), ("gamma", "Gamma"),
                     ("outlow", "Out Low"), ("outhigh", "Out High"), ("doclamp", "Clamp")):
        _promote(r, inp, "%s_%s" % (ch, inp), "%s %s" % (label, lab))
    return r


def _vec2_node(sub, typ, name, *inputs):
    n = sub.createNode(typ, name)
    if n.parm("signature"):
        n.parm("signature").set("vector2")
    for i, src in enumerate(inputs):
        if src is not None:
            n.setInput(i, src)
    return n


def _uv_transform(sub):
    """Shared UV transform for all textures: tiling / offset / rotate (place2d).

    Applied inside each UDIM tile: uv = tile + wrap(place2d(uv - tile)), so tiling never
    reads other UDIM tiles (wrong texture; red on Arnold GPU). Identity at defaults.
    Nodes are named uv_* (no channel prefix, never removed).
    """
    tc = sub.createNode("mtlxtexcoord", "uv_texcoord")
    tc.parm("signature").set("vector2")
    tile = _vec2_node(sub, "mtlxfloor", "uv_tile", tc)
    local = _vec2_node(sub, "mtlxsubtract", "uv_local", tc, tile)
    # place2d divides UVs by its scale (scale = texture size; verified in Karma + Arnold).
    # Expose the industry-style repeat count instead: scale = 1 / uv_tiling.
    inv = _vec2_node(sub, "mtlxdivide", "uv_tiling_inv")
    inv.parmTuple("in1_vector2").set((1.0, 1.0))
    _promote(inv, "in2", "uv_tiling", "UV Tiling")
    place = sub.createNode("mtlxplace2d", "uv_place2d")
    place.setInput(place.inputIndex("texcoord"), local)
    place.parmTuple("pivot").set((0.5, 0.5))
    place.setInput(place.inputIndex("scale"), inv)
    _promote(place, "offset", "uv_offset", "UV Offset")
    _promote(place, "rotate", "uv_rotate", "UV Rotate")
    wrap = _vec2_node(sub, "mtlxmodulo", "uv_wrap", place)
    wrap.parmTuple("in2_vector2").set((1.0, 1.0))
    return _vec2_node(sub, "mtlxadd", "uv_out", tile, wrap)


def build_template(matlib, name="template"):
    """(Re)build the template MaterialX material inside ``matlib``."""
    old = matlib.node(name)
    if old:
        old.destroy()
    sub = matlib.createNode("subnet", name)
    _setup_mtlx_subnet(sub)
    for c in sub.children():
        c.destroy()

    surf = sub.createNode("mtlxstandard_surface", "mtlxstandard_surface")
    surf_out = _connector(sub, "surface", "Surface", "surface", surf)
    disp_out = _connector(sub, "displacement", "Displacement", "displacement", None)
    uv = _uv_transform(sub)

    for ch, d in CHANNELS:
        kind, label = d["kind"], d["label"]
        img = sub.createNode("mtlximage", ch + "_image")
        img.setInput(img.inputIndex("texcoord"), uv)
        # Per-iteration texture: template lives at <hda>/materials/template/<node>.
        hda = "hou.node('../../..')"
        img.parm("file").setExpression(
            "%s.hdaModule().chan_file(%s, '%s')" % (hda, hda, ch), hou.exprLanguage.Python)
        img.parm("filecolorspace").setExpression(
            "%s.hdaModule().chan_colorspace(%s, '%s')" % (hda, hda, ch), hou.exprLanguage.Python)
        if kind == "color":
            img.parm("signature").set("color3")
            last = _range(sub, ch, label, "color3", img)
            if d.get("hsv"):
                hsv = sub.createNode("mtlxhsvadjust", ch + "_hsv")
                hsv.parm("signature").set("color3")
                hsv.setInput(0, last)
                _promote(hsv, "amount", ch + "_hsv", label + " HSV Adjust")
                last = hsv
            surf.setInput(surf.inputIndex(d["target"]), last)
        elif kind == "float":
            img.parm("signature").set("float")
            last = _range(sub, ch, label, "float", img)
            surf.setInput(surf.inputIndex(d["target"]), last)
        elif kind == "normal":
            img.parm("signature").set("vector3")
            nm = sub.createNode("mtlxnormalmap", ch + "_normalmap")
            nm.setInput(0, img)
            _promote(nm, "scale", ch + "_scale", "Normal Scale")
            surf.setInput(surf.inputIndex("normal"), nm)
        elif kind == "height":
            img.parm("signature").set("float")
            # Height maps are usually 0..1 around 0.5 -> remap to -0.5..0.5.
            last = _range(sub, ch, label, "float", img, dict(outlow=-0.5, outhigh=0.5))
            disp = sub.createNode("mtlxdisplacement", ch + "_displacement")
            disp.setInput(0, last)
            disp.parm("scale").set(0.01)
            scale = _promote(disp, "scale", ch + "_scale", "Height Scale")
            disp_out.setInput(0, disp)
            # Same height as bump on top of the normal map ("Height as: Bump"); the
            # unused one (bump or displacement) is pruned per the HDA's height_mode.
            bump = sub.createNode("mtlxbump", ch + "_bump")
            bump.setInput(bump.inputIndex("height"), last)
            bump.setInput(bump.inputIndex("scale"), scale)
            ni = surf.inputIndex("normal")
            if surf.input(ni) is not None:
                bump.setInput(bump.inputIndex("normal"), surf.input(ni))
            surf.setInput(ni, bump)

    # Emission weight lives in the emission branch: removed (-> 0) when there is no map.
    surf.parm("emission").set(1.0)
    p = _promote(surf, "emission", "emission_weight", "Emission Weight")
    p.setName("emission_weight", unique_name=True)
    surf.parm("emission").set(0.0)

    sub.layoutChildren()
    matlib.layoutChildren()
    return sub


# ---------------------------------------------------------------------------------------
# Patterns UI helpers
# ---------------------------------------------------------------------------------------

def reset_patterns(node):
    mp = node.parm("channels")
    mp.set(0)
    mp.set(len(DEFAULT_PATTERNS))
    for i, (ch, tokens, cs, en) in enumerate(DEFAULT_PATTERNS, 1):
        node.parm("ch_enable%d" % i).set(en)
        node.parm("ch_target%d" % i).set(ch)
        node.parm("ch_tokens%d" % i).set(tokens)
        node.parm("ch_colorspace%d" % i).set(cs)


def on_created(node):
    reset_patterns(node)


# ---------------------------------------------------------------------------------------
# Scanning / parsing
# ---------------------------------------------------------------------------------------

def _patterns(node):
    pats = []
    for i in range(1, node.evalParm("channels") + 1):
        if not node.evalParm("ch_enable%d" % i):
            continue
        ch = node.evalParm("ch_target%d" % i)
        tokens = node.evalParm("ch_tokens%d" % i).strip()
        if not tokens:
            continue
        try:
            rx = re.compile(r"(?<![A-Za-z0-9])(?:%s)(?![A-Za-z0-9])" % tokens, re.I)
        except re.error as e:
            raise hou.NodeError("Channel row %d (%s): bad regex %r: %s" % (i, ch, tokens, e))
        pats.append((ch, rx, node.evalParm("ch_colorspace%d" % i), i))
    return pats


def _sanitize(name):
    name = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_")
    if not name:
        return "material"
    if name[0].isdigit():
        name = "m_" + name
    return name


def _common_prefix(names):
    if len(names) < 2:
        return ""
    p = os.path.commonprefix(names)
    # cut back to a separator so we never split a word
    cut = max(p.rfind(c) for c in SEPS)
    p = p[:cut + 1] if cut >= 0 else ""
    # never eat a whole material name
    if any(len(n) <= len(p) for n in names):
        return ""
    return p


def parse_name(stem, pats, custom_rx=None):
    """-> (material, channel, row) or None. ``stem`` has no extension / UDIM."""
    if custom_rx is not None:
        m = custom_rx.search(stem)
        if not m:
            return None
        mat, chtxt = m.group("material"), m.group("channel")
        for ch, rx, cs, row in pats:
            if rx.fullmatch(chtxt):
                return mat, ch, row
        return None
    best = None
    for ch, rx, cs, row in pats:
        for m in rx.finditer(stem):
            if (best is None or m.start() > best[0].start()
                    or (m.start() == best[0].start() and m.end() > best[0].end())):
                best = (m, ch, row)
    if best is None:
        return None
    m, ch, row = best
    return stem[:m.start()].rstrip(SEPS), ch, row


def scan(node):
    """-> (materials {name: {channel: (path, colorspace)}}, report lines)."""
    raw_dir = node.parm("texdir").unexpandedString().strip().replace("\\", "/").rstrip("/")
    abs_dir = hou.text.expandString(raw_dir)
    if not raw_dir or not os.path.isdir(abs_dir):
        raise hou.NodeError("Texture directory not found: %s" % (abs_dir or "<empty>"))

    exts = [e.lower().lstrip(".") for e in node.evalParm("extensions").split()]
    pats = _patterns(node)
    if not pats:
        raise hou.NodeError("No enabled channel patterns.")
    custom = node.evalParm("custom_regex").strip()
    custom_rx = None
    if custom:
        try:
            custom_rx = re.compile(custom, re.I)
        except re.error as e:
            raise hou.NodeError("Custom regex: %s" % e)
        if not {"material", "channel"} <= set(custom_rx.groupindex):
            raise hou.NodeError("Custom regex needs (?P<material>...) and (?P<channel>...)")
    cs_by_row = {row: cs for _, _, cs, row in pats}

    files = []
    if node.evalParm("recursive"):
        for root, _, fs in os.walk(abs_dir):
            rel = os.path.relpath(root, abs_dir).replace("\\", "/")
            files += [f if rel == "." else rel + "/" + f for f in fs]
    else:
        files = [f for f in os.listdir(abs_dir) if os.path.isfile(os.path.join(abs_dir, f))]

    found = {}      # (raw material, channel) -> {ext: (relpath, row)}
    skipped = []
    for rel in sorted(files):
        base = rel.rsplit("/", 1)[-1]
        stem, ext = os.path.splitext(base)
        ext = ext.lower().lstrip(".")
        if ext not in exts:
            continue
        udim = UDIM_RE.search(stem)
        if udim:
            stem = stem[:udim.start()].rstrip(".")
            stem_dir = rel[:len(rel) - len(base)]
            rel = stem_dir + base[:udim.start()] + "<UDIM>" + base[udim.end():]
        parsed = parse_name(stem, pats, custom_rx)
        if not parsed:
            skipped.append(base)
            continue
        mat, ch, row = parsed
        if not mat:   # file named just "BaseColor.png" -> use folder name
            mat = os.path.basename(os.path.dirname(os.path.join(abs_dir, rel))) or "material"
        found.setdefault((mat, ch), {}).setdefault(ext, (rel, row))

    raw_names = sorted({m for m, _ in found})
    prefix = _common_prefix(raw_names) if node.evalParm("strip_common") else ""
    name_prefix = node.evalParm("name_prefix")

    mats, report = {}, []
    for (mat, ch), by_ext in sorted(found.items()):
        ext = next((e for e in exts if e in by_ext), None)
        rel, row = by_ext[ext]
        name = _sanitize(name_prefix + mat[len(prefix):])
        mats.setdefault(name, {})[ch] = (raw_dir + "/" + rel, cs_by_row.get(row, ""))
        if len(by_ext) > 1:
            report.append("  %s.%s: picked .%s over %s" % (name, ch, ext,
                          ", ".join("." + e for e in by_ext if e != ext)))

    head = ["%d materials from %s" % (len(mats), raw_dir)]
    if prefix:
        head.append("stripped common prefix '%s'" % prefix)
    for name in sorted(mats):
        head.append("  %-28s %s" % (name, " ".join(c for c in CHANNEL_KEYS if c in mats[name])))
    if skipped:
        head.append("unmatched files (%d): %s%s" % (len(skipped), ", ".join(skipped[:20]),
                                                    " ..." if len(skipped) > 20 else ""))
    return mats, head + report


# ---------------------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------------------

# Neutral value written into placeholder tiles (what "no texture" should mean per channel).
FILL_VALUES = {
    "basecolor": (0.18, 0.18, 0.18), "emission": (0.0, 0.0, 0.0), "opacity": (1.0, 1.0, 1.0),
    "metalness": (0.0,), "roughness": (0.5,), "specular": (1.0,),
    "normal": (0.5, 0.5, 1.0), "height": (0.5,),
}


def _tiles(abs_pattern):
    """{udim: abs file} for a path containing <UDIM>."""
    d, base = os.path.split(abs_pattern)
    pre, post = base.split("<UDIM>")
    out = {}
    if os.path.isdir(d):
        for f in os.listdir(d):
            if f.startswith(pre) and f.endswith(post):
                mid = f[len(pre):len(f) - len(post)]
                if len(mid) == 4 and mid.isdigit():
                    out[int(mid)] = os.path.join(d, f)
    return out


def _write_tile(path, value):
    import OpenImageIO as oiio
    import numpy as np
    n = len(value)
    spec = oiio.ImageSpec(4, 4, n, oiio.HALF)
    buf = oiio.ImageBuf(spec)
    buf.set_pixels(oiio.ROI(0, 4, 0, 4, 0, 1, 0, n),
                   np.tile(np.array(value, dtype=np.float32), (4, 4, 1)))
    if not buf.write(path):
        raise hou.NodeError("Could not write placeholder tile %s: %s" % (path, buf.geterror()))


def _try_remove(path):
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass        # locked by a renderer; harmless leftover


def fill_udims(node, mats, report):
    """Make every UDIM channel of a material cover the same tiles.

    Renderers differ on missing tiles: Karma / Arnold CPU treat them as empty, Arnold GPU
    (Hydra) paints the whole shader red. For channels missing tiles that other channels
    of the same material have, build <filldir>/<material>/<channel>/ with hard links to
    the real tiles plus 4x4 neutral placeholder tiles, and point the channel there.
    """
    import shutil
    fill_raw = node.parm("filldir").unexpandedString().strip().replace("\\", "/").rstrip("/")
    fill_abs = hou.text.expandString(fill_raw)
    for name, chans in mats.items():
        tiles = {ch: _tiles(hou.text.expandString(p)) for ch, (p, cs) in chans.items()
                 if "<UDIM>" in p}
        union = set().union(*tiles.values()) if tiles else set()
        for ch, have in tiles.items():
            missing = sorted(union - set(have))
            sub_abs = os.path.join(fill_abs, name, ch)
            if not missing or not have:
                if os.path.isdir(sub_abs):
                    shutil.rmtree(sub_abs, ignore_errors=True)
                continue
            os.makedirs(sub_abs, exist_ok=True)
            src_pattern, cs = chans[ch]
            base = src_pattern.rsplit("/", 1)[-1]
            # Incremental: files may be open (locked) by a running renderer/viewport.
            wanted = set()
            for t, src in have.items():
                dst = os.path.join(sub_abs, os.path.basename(src))
                wanted.add(os.path.basename(dst))
                if os.path.exists(dst) and os.path.samefile(src, dst):
                    continue
                _try_remove(dst)
                try:
                    os.link(src, dst)
                except OSError:
                    shutil.copy2(src, dst)
            for t in missing:
                dst = os.path.join(sub_abs, base.replace("<UDIM>", str(t)))
                wanted.add(os.path.basename(dst))
                if not os.path.exists(dst):
                    _write_tile(dst, FILL_VALUES.get(ch, (0.0,)))
            for f in os.listdir(sub_abs):
                if f not in wanted:
                    _try_remove(os.path.join(sub_abs, f))
            chans[ch] = ("%s/%s/%s/%s" % (fill_raw, name, ch, base), cs)
            report.append("  %s.%s: filled missing tiles %s" % (name, ch,
                          " ".join(str(t) for t in missing)))


# ---------------------------------------------------------------------------------------
# Stateless evaluation (called from expressions / Python LOP inside the HDA's For Each loop)
# ---------------------------------------------------------------------------------------

_CACHE = {}     # scan results keyed by every parameter that affects them + folder mtime


def _scan_key(node):
    texdir = hou.text.expandString(node.parm("texdir").unexpandedString())
    try:
        mtime = os.stat(texdir).st_mtime
    except OSError:
        mtime = None
    vals = [p.unexpandedString() if p.parmTemplate().type() == hou.parmTemplateType.String
            else p.eval() for p in node.parms()
            if p.name() not in ("report",) and not p.name().startswith("f_")]
    return (node.sessionId(), mtime, tuple(map(str, vals)))


def materials(node):
    """{material: {channel: (path, colorspace)}} for the node's current parameters."""
    key = _scan_key(node)
    hit = _CACHE.get(node.sessionId())
    if hit and hit[0] == key:
        return hit[1]
    mats, report = scan(node)
    if node.evalParm("fill_udims"):
        fill_udims(node, mats, report)
    if node.evalParm("height_mode") == "off":
        for chans in mats.values():
            chans.pop("height", None)
    _CACHE[node.sessionId()] = (key, mats, report)
    return mats


def material_names(node):
    """Space-separated material names: drives the For Each loop."""
    try:
        return " ".join(sorted(materials(node)))
    except hou.Error:
        return ""


def _current(node):
    return materials(node).get(hou.contextOption("ITERATIONVALUE") or "", {})


def chan_file(node, ch):
    # expression results aren't variable-expanded like literal parm values
    return hou.text.expandString(_current(node).get(ch, ("", ""))[0])


def chan_colorspace(node, ch):
    return _current(node).get(ch, ("", ""))[1]


def prune_material(node, stage):
    """Inside the loop: strip what this material doesn't use.

    * channels without a texture: shader prims named <channel>_*, material inputs named
      <channel>_* and every connection to them (surface inputs fall back to defaults;
      emission_weight goes with the emission branch -> emission 0 without a map);
    * height_mode: "displacement" removes height_bump, "bump" removes height_displacement.
    Pass-through nodes (height_bump) are bypassed: connections to them are redirected to
    whatever feeds their "normal" input, so the normal map survives without the bump.
    """
    from pxr import Sdf, UsdShade
    name = hou.contextOption("ITERATIONVALUE") or ""
    chans = materials(node).get(name)
    if chans is None:
        return
    mat_path = node.evalParm("matprefix").rstrip("/") + "/" + name
    mat = stage.GetPrimAtPath(mat_path)
    if not mat:
        return
    missing = tuple(ch + "_" for ch in CHANNEL_KEYS if ch not in chans)
    extra = {"displacement": ("height_bump",), "bump": ("height_displacement",)}.get(
        node.evalParm("height_mode"), ())
    removed_prims = [str(p.GetPath()) for p in mat.GetChildren()
                     if (missing and p.GetName().startswith(missing)) or p.GetName() in extra]
    if not removed_prims:
        return
    removed_inputs = [a.GetPath() for a in mat.GetAttributes()
                      if missing and a.GetName().startswith("inputs:")
                      and a.GetName()[7:].startswith(missing)]

    def dead(src):
        s = str(src)
        return (any(s == p or s.startswith(p + ".") for p in removed_prims)
                or src in removed_inputs)

    # bypass map: <removed prim>.outputs:out -> live source of its inputs:normal
    bypass = {}
    for p in removed_prims:
        a = stage.GetPrimAtPath(p).GetAttribute("inputs:normal")
        if a:
            live = [c for c in a.GetConnections() if not dead(c)]
            if live:
                bypass[Sdf.Path(p + ".outputs:out")] = live[0]

    for prim in [mat] + list(mat.GetChildren()):
        if str(prim.GetPath()) in removed_prims:
            continue
        for attr in prim.GetAttributes():
            cons = attr.GetConnections()
            if cons and any(dead(c) for c in cons):
                keep = [bypass.get(c, c) for c in cons if not dead(c) or c in bypass]
                if keep:
                    attr.SetConnections(keep)
                else:
                    attr.ClearConnections()
    for p in removed_prims:
        stage.RemovePrim(p)
    for a in removed_inputs:
        mat.RemoveProperty(a.name)


def rescan(node):
    """Button: forget the cached scan, show the report, recook."""
    _CACHE.pop(node.sessionId(), None)
    try:
        materials(node)
        report = _CACHE[node.sessionId()][2]
    except hou.Error as e:
        report = ["ERROR: %s" % e]
    node.parm("report").set(chr(10).join(report))
    node.cook(force=True)
