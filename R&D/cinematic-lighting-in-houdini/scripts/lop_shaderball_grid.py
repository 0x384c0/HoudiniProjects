# Shader-ball grid: one ball per material matching the pattern, laid out in a grid.
# Re-cooks whenever the input stage changes (new/removed materials -> new/removed balls).
import fnmatch, glob, math, os, re
import numpy as np
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade, Vt

node = hou.pwd()
stage = node.editableStage()

patterns = node.evalParm("matpattern").split()
src_path = node.evalParm("srcball")
surf_rel = node.evalParm("surface")
parent_path = node.evalParm("parentpath").rstrip("/")
cols = node.evalParm("columns")
spacing = node.evalParm("spacing")
udim_offset = node.evalParm("udim_offset")
fit_cam = node.evalParm("fitcam")
cam_path = node.evalParm("camera")

src = stage.GetPrimAtPath(src_path)
if not src:
    raise hou.NodeError("Source shader ball not found: " + src_path)

mats = [p for p in stage.Traverse()
        if p.IsA(UsdShade.Material)
        and any(fnmatch.fnmatchcase(str(p.GetPath()), pat) for pat in patterns)]
mats.sort(key=lambda p: p.GetName())
n = len(mats)
if not n:
    raise hou.NodeWarning("No materials match: " + " ".join(patterns))

cols = cols if cols > 0 else int(math.ceil(math.sqrt(n)))
rows = int(math.ceil(n / float(cols)))

UDIM = re.compile(r"\.(1\d{3})\.")


def first_udim(mat):
    """First UDIM tile of the material's base color texture (1001 if none / not UDIM)."""
    shaders = [p for p in Usd.PrimRange(mat) if p.IsA(UsdShade.Shader)]
    shaders.sort(key=lambda p: (p.GetName() != "basecolor_image", p.GetName()))
    for p in shaders:
        a = p.GetAttribute("inputs:file")
        v = a.Get() if a else None
        if not v or "<UDIM>" not in v.path:
            continue
        tiles = sorted(int(m.group(1)) for f in glob.glob(v.path.replace("<UDIM>", "[0-9][0-9][0-9][0-9]"))
                       for m in [UDIM.search(os.path.basename(f))] if m)
        if tiles:
            return tiles[0]
    return 1001


# Hide the source ball (instances re-enable visibility on themselves).
UsdGeom.Imageable(src).CreateVisibilityAttr().Set(UsdGeom.Tokens.invisible)
UsdGeom.Scope.Define(stage, parent_path) if not stage.GetPrimAtPath(parent_path) else None

src_mesh = stage.GetPrimAtPath(src_path + "/" + surf_rel)
src_st = UsdGeom.PrimvarsAPI(src_mesh).GetPrimvar("st") if src_mesh else None
st_np = np.array(src_st.Get(), dtype=np.float32) if src_st and src_st.Get() is not None else None
st_tile = np.clip(st_np, 0.0, 1.0) if st_np is not None else None

xs, zs = [], []
for i, mat in enumerate(mats):
    c, r = i % cols, i // cols
    x = (c - (cols - 1) / 2.0) * spacing
    z = (r - (rows - 1) / 2.0) * spacing
    xs.append(x); zs.append(z)
    path = "%s/%s" % (parent_path, mat.GetName())
    inst = stage.DefinePrim(path, "Xform")
    inst.GetReferences().AddInternalReference(src.GetPath())
    xf = UsdGeom.Xformable(inst)
    xf.ClearXformOpOrder()
    xf.AddTranslateOp().Set(Gf.Vec3d(x, 0, z))
    UsdGeom.Imageable(inst).CreateVisibilityAttr().Set(UsdGeom.Tokens.inherited)
    UsdShade.MaterialBindingAPI.Apply(inst).Bind(UsdShade.Material(mat))
    inst.SetCustomDataByKey("lookdev:material", str(mat.GetPath()))
    # Shader-ball UVs cover 0..1 = tile 1001 only; shift them onto the material's first tile.
    if udim_offset and st_np is not None:
        t = first_udim(mat)
        if True:
            u, v = (t - 1001) % 10, (t - 1001) // 10
            mesh = stage.GetPrimAtPath(path + "/" + surf_rel)
            pv = UsdGeom.PrimvarsAPI(mesh).GetPrimvar("st")
            # squeeze into the tile so filtering at the UV seam never reads the neighbour
            # tile (missing tiles = red "bad texture" on Arnold GPU)
            inset = 0.004 + st_tile * (1.0 - 0.008)
            pv.Set(Vt.Vec2fArray.FromNumpy(inset + np.array([u, v], dtype=np.float32)))
        inst.SetCustomDataByKey("lookdev:udim", t)
    else:
        inst.SetInstanceable(True)

# Frame the grid with the camera, keeping its viewing direction.
cam = stage.GetPrimAtPath(cam_path)
if fit_cam and cam and cam.IsA(UsdGeom.Camera):
    ucam = UsdGeom.Camera(cam)
    m = UsdGeom.Xformable(cam).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
    right = Gf.Vec3d(m[0][0], m[0][1], m[0][2]).GetNormalized()
    up = Gf.Vec3d(m[1][0], m[1][1], m[1][2]).GetNormalized()
    back = Gf.Vec3d(m[2][0], m[2][1], m[2][2]).GetNormalized()   # camera looks down -Z
    ball_h, half = 0.5, spacing / 2.0
    x0, x1, z0, z1 = min(xs) - half, max(xs) + half, min(zs) - half, max(zs) + half
    center = Gf.Vec3d((x0 + x1) / 2.0, ball_h / 2.0, (z0 + z1) / 2.0)
    f = ucam.GetFocalLengthAttr().Get()
    # 16:9 output, aperture conformed by expanding (what Karma does with a square aperture)
    hap = ucam.GetHorizontalApertureAttr().Get()
    vap = ucam.GetVerticalApertureAttr().Get() or hap * 9.0 / 16.0
    aspect = 16.0 / 9.0
    if hap / vap < aspect:
        hap = vap * aspect
    else:
        vap = hap / aspect
    tan_h, tan_v = hap / (2.0 * f), vap / (2.0 * f)
    # Author the 16:9 aperture so renderers without aperture conforming (Arnold) frame the same.
    ucam.GetHorizontalApertureAttr().Set(hap)
    ucam.GetVerticalApertureAttr().Set(vap)
    dist = 0.0
    for cx in (x0, x1):
        for cy in (0.0, ball_h):
            for cz in (z0, z1):
                d = Gf.Vec3d(cx, cy, cz) - center
                px, py, pz = d * right, d * up, d * back
                dist = max(dist, pz + abs(px) / tan_h, pz + abs(py) / tan_v)
    dist *= 1.05
    eye = center + back * dist
    mm = Gf.Matrix4d(m.ExtractRotationMatrix(), eye)
    xf = UsdGeom.Xformable(cam)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(mm)
    if ucam.GetClippingRangeAttr():
        ucam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 10000))
