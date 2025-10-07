# CLAUDE.md

`HoudiniProjects` git repo: one folder per Houdini project (`R&D/<project>/` etc., each folder is `$HIP`). Rules below apply to every project; a project's own `CLAUDE.md` holds only what is specific to it.

Paths use environment variables, not host-specific locations. Resolve them on the current machine (inside Houdini/hython: `hou.text.expandString('$HFS')` etc.).

## Files and storage

- A project folder (`$HIP`) holds project files only: `.hip` scenes, scripts, and at most small data (configs, small reference files).
- Everything large or generated — downloaded maps, assets, geometry/sim caches, USD layers, textures, renders, flipbooks — goes under `$HIP_CACHE`, never in `$HIP`.
- Point every file-writing node (File Cache, ROP Output, USD Render ROP, Karma output, SOP Create layer save path, Download File, etc.) at a `$HIP_CACHE/...` path.
- `$HIP_CACHE` = `F:/home/houdini_cache`, set by `set -g` inside each `.hip` (Aliases and Variables, not the shell env); change it there for another machine.
- Name texture files with a colorspace suffix (`_srgb_tx`, `_Raw`, `_ACEScg`, …) so the OCIO file rules pick the right space (see below).
- `backup/` (and `hda/backup/`) folders are Houdini auto-backups. Don't edit; don't commit.

## Tools / versions

- Houdini 22.0.x: install dir is `$HFS` (`$HFS/bin/hython`, `husk`, `iconvert`, `iinfo`). hython has PyOpenColorIO 2.5, OpenImageIO, pxr. `$HFS` is not set in the shell; on this machine Houdini is under `F:/Program Files/Side Effects Software/Houdini 22.0.<build>`.
- HtoA 6.5.4 / Arnold 7.5.4: install dir is `$HTOA_ROOT` (set by the `htoa.json` package); binaries in `$HTOA_ROOT/scripts/bin` (`kick`, `oiiotool`, `maketx`).
- Nuke 17.0 (OCIO 2.4.2), Indie license: run scripts with `Nuke17.0 --indie -t script.py`.
- Houdini user prefs: `$HOUDINI_USER_PREF_DIR` (packages: `htoa.json`, `fxhoudinimcp.json`).
- Shared Houdini env settings are in `houdini.env` at the repo root.

## Color management

- `$OCIO` (user env) points to an ACES studio config built from AcademySoftwareFoundation/OpenColorIO-Config-ACES (local branch `custom` from tag `v3.0.0`, file `studio-config-v3.0.0_aces-v2.0_ocio-v2.4.ocio`). Always read the location from `$OCIO`.
- ACES 2.0 config, OCIO profile 2.4 — the newest that Nuke 17 (OCIO 2.4) can read; ACES v4.0.0 configs are profile 2.5 only. Views are `ACES 2.0 - SDR 100 nits (Rec.709)` etc.; ACES 1.x views are gone. Default display `sRGB - Display`.
- Rendering space ACEScg. Local edits vs. upstream: roles `default_byte/default_float/default_sequencer`, `Gamma2.2` alias (for Nuke), and name-based `file_rules`.
- `file_rules` are GENERATED: edit `custom/build_file_rules.py` in the config repo, then `hython build_file_rules.py` (rewrites block + runs checks; `--check` only checks). Colorspace comes from the last word of the file name before UDIM/frame + extension, case-insensitive (`_Raw`, `_ACEScg`, `_srgb_tx`, `_lin_srgb`, … and data maps `_Normal`, `_Height`, `_Roughness`, `_Metallic`, `_AO`, `_Mask`… → Raw); then extension fallbacks (exr → ACEScg, 8-bit → sRGB - Texture, hdr → Linear Rec.709).
- OCIO rule gotchas (verified): globs and regexes are case-sensitive and must match the WHOLE path; Houdini/Karma ignores catch-all `pattern: "*"` rules (falls back to OIIO's "Linear" = lin_rec709), so all rules are regex.
- Who honours file rules: Karma (UsdUVTexture / mtlximage colorspace `auto`) ✓, Nuke Read `default` ✓. Arnold 7.5.4 does NOT — image `color_space = auto` is just 8-bit → sRGB, float → rendering space. ACEScg/Raw EXRs pass through unchanged; 8-bit data maps or EXRs in other spaces need `color_space` set explicitly on the Arnold image node.
- Arnold: the `$OCIO` env var overrides the `color_manager_ocio.config` parameter.

## Karma vs Arnold gotchas (verified)

- Dome light: set Texture Format to `latlong`. With `automatic`, Arnold 7.5.4 mis-maps lat-long HDRIs (sun ~90° off, too high, ~1.75× too bright); Karma is correct either way.
- Camera aperture: Karma conforms a square aperture to the output aspect (expandAperture); Arnold doesn't, so it frames tighter. Author an aperture matching the output aspect.
- Karma XPU metals render slightly lighter than Arnold; that's expected, not a bug.
- Arnold GPU paints a shader red when it reads a missing UDIM tile; Karma and Arnold CPU treat missing tiles as empty. `arnold:global:error_color_bad_texture` fixes it in kick but Hydra (viewport/husk) ignores it, so the fix has to be in the data (no missing tiles).
- Arnold GPU has no CPU fallback or geometry streaming (unlike Karma XPU): heavy displacement can fill VRAM and crash (CUDA access violation).
- Arnold option attributes on RenderSettings: Hydra (Houdini viewport, husk, HtoA LOPs) uses `arnold:global:<option>`, kick's USD procedural uses `arnold:<option>`. HtoA's Arnold Render Settings LOP writes only the `arnold:global:` form, so for kick tests author the `arnold:` form too.
- Arnold GPU speckle/"semi-transparent" look at default AA is sampling noise (clean at AA 8), not a material problem.
- Arnold viewport keeps its render device until the delegate restarts: switching between nodes with and without `render_device = GPU` can leave it on the old device. Switch to VK and back to force a restart.
- Arnold can't read `.rat`; convert with `iconvert` (e.g. Houdini's bundled `$HFS/houdini/pic/hdri/*.rat`).

## Headless workflow (hython / husk / kick)

- Scene edits can run without the GUI: `hython script.py` → `hou.hipFile.load(...)`, edit, `hou.hipFile.save()`. Close Houdini first (or don't save) so the GUI session doesn't overwrite it.
- Cook TOPs headless: `hou.node('/tasks/top/<node>').cookWorkItems(block=True)`.
- Karma: `$HFS/bin/husk --renderer BRAY_HdKarmaXPU --res 640 360 -o out.exr scene.usda` (export the LOP stage with `node.stage().Flatten().Export(...)`).
- Hydra Arnold (same engine as the viewport) headless: run husk from a hython whose `HOUDINI_USER_PREF_DIR` points at the prefs dir with the htoa package (so HtoA's env loads), via `subprocess` with `os.environ`: `husk --renderer HdArnoldRendererPlugin -o out.exr scene.usda`. Plain husk from a shell fails ("unable to allocate plugin").
- Arnold without Hydra: `$HTOA_ROOT/scripts/bin/kick -i scene.usda -o out.exr -dw -dp` (honours RenderSettings and `arnold:*` attrs).
- HtoA in hython with only `HOUDINI_PATH` set to `$HTOA_ROOT`: its Python can't load `ai.dll` (Python ignores PATH for DLLs), so HtoA LOPs (e.g. `arnold_rendersettings`) can't be built headless. GUI Houdini loads HtoA via the package.
- Git Bash mangles args that look like paths (`/tasks/top/...`, `/stage/...`, `/World/Camera`) and the scratchpad's `/f/...` script paths: run with `MSYS_NO_PATHCONV=1` and pass Windows-style paths (`F:/...`).
- Image checks: HtoA's `oiiotool` has no OCIO and Houdini's OIIO can't read `.rat`; use hython's PyOpenColorIO + OpenImageIO (`ImageBufAlgo.ociodisplay`) for display transforms, `iconvert` for `.rat`.

## Houdini Python API gotchas

- Python Script LOP: the code is a string parm, so `$VAR` in it gets expanded (even in comments). Avoid `$` in LOP code.
- Edit Material Properties: cook the node before `createparms.pressButton()`, else no parms are made. Parm names are encoded (`xn__inputs…`); map them with `hou.text.decodeParm()` (`inputs:<name>`, `inputs:<name>_control` = `set`).
- Render Settings LOPs: the Y resolution (`resolutiony` / `resolution2`) is locked with an expression from the camera aspect; set `res_mode = manual` where present, then `lock(False)` + `deleteAllKeyframes()` before setting it.
- SOP Create LOP: prims land under `pathprefix` (default `/$OS`), not `primpath`; set both.
- Karma Material Builder in Python: material library → `createNode('subnet')` → `voptoolutils._setupMtlXBuilderSubnet(subnet_node=..., mask=voptoolutils.KARMAMTLX_TAB_MASK, folder_label='Karma Material Builder')`. Fine in hython; don't run it through the MCP bridge.
- Node type names differ from labels: UV Texture SOP is `texture`; distant light LOP is `distantlight::2.0`. USD Render ROP is a ROP node (no display flag).
- Duplicate LOP: `ncy` counts the source (copy 0 replaces it); set `makeinstances = 0` to bind materials per copy.
- `createDigitalAsset` refuses `matnode = *` on Material Library nodes as external refs; pass `ignore_external_references=True`, and `create_backup=False` to avoid `hda/backup/`.

## Houdini MCP server

- FXHoudini-MCP: installed via the `fxhoudinimcp.json` package (its `FXHOUDINIMCP` path points into the server's venv); start the server with the `run_mcp.bat` in its install folder (stdio).
- Houdini must be running with the project's `.hip` open for the MCP tools to work on the scene.
- Prefer inspecting/editing the scene through the MCP tools (or headless hython) over parsing `.hip` files, which are binary-ish and not meant to be hand-edited.
- MCP HTTP bridge (port 8100) pitfalls: `voptoolutils._setupMtlXBuilderSubnet` crashed the live session; `hdefereval.executeInMainThreadWithResult` deadlocked it (the bridge already runs on the main thread, so it waits on itself; Houdini had to be killed). Never use hdefereval through the bridge; keep bridge calls to small reads/parm sets and do node building in hython with Houdini closed.

## Git

- The user handles all git operations manually. Don't commit, amend, push, stage or run gc; don't offer to.
- GitHub is only a file backup, not a history: work is folded into the last commit and force-pushed with `R&D/amend_commit.bat`.
- Only `.hip` and small project files belong in the repo; save the scene before the user syncs.

## Conventions

- Debug material/render issues on a reduced scene first: isolate the affected parts (prune/deactivate the rest), move the camera close, low resolution/samples. Keep each test ~1 min and a few GB; scale up only after the cause is found.
- Materials are MaterialX only (stdlib nodes). When a project renders with both Karma and Arnold, the same MaterialX network serves both: no renderer-specific shaders (no Arnold shader networks, no `arnold:surface` outputs).
- Prefer existing nodes and their parameters over custom Python. Before writing a Python LOP, a script or raw USD attributes, check whether a built-in or HtoA node already exposes the setting: search the node's parms (e.g. `hou.text.decodeParm` over `node.parms()`, `parm.containingFolders()` to find the UI tab) and the docs. Example: the Arnold Auto-Tx Path is on Arnold Render Settings > Rendering > Texture; a custom Python LOP for it was redundant. Use Python only for what nodes can't do.
