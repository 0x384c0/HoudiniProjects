# CLAUDE.md

Houdini R&D project: planets — Earth rendered with Karma XPU from NASA Blue Marble maps. Shared rules (storage, `$HIP_CACHE`, OCIO, tools, headless workflow, git, conventions) are in the repo-root `CLAUDE.md`.

## Layout

- `planets.hip` — main scene (frame range 1–1).

## Scene

- `/tasks/top` (TOP network), cook `render_earth` to run everything:
  - `download_maps` (Download File) — fetches the NASA maps into `$HIP_CACHE/planets/earth/tex/`. Cache mode skips files that already exist.
    - Blue Marble NG Jan 2004 `world.200401.3x21600x10800.jpg` → `earth_bmng_200401_srgb_tx.jpg`
    - GEBCO 08 elevation `gebco_08_rev_elev_21600x10800.jpg` → `earth_gebco08_elev_Raw.jpg`
  - `wait_downloads` (Wait for All) → `render_earth` (ROP Fetch of `/stage/render_earth`).
- `/stage` (LOPs):
  - `earth_geo` (SOP Create, prim `/earth/mesh_0`) — polymesh sphere r=1, 361×720, polar vertex UVs with Fix Boundary Seams. Layer save path `$HIP_CACHE/planets/usd/`.
  - `earth_materials` — Karma Material Builder `earth_mtl` (`/materials/earth_mtl`): `mtlximage` color → `mtlxstandard_surface` base_color; elevation `mtlximage` (float) → `mtlxdisplacement` (scale 0.01, exaggerated). Bound to `/earth`.
  - `camera` (`/cameras/camera`, 16:9 aperture), `sun` (distant light, angle 0.53°).
  - `karma_settings` — engine XPU, 1920×1080, output `$HIP_CACHE/render/earth.$F4.exr`.
  - `render_earth` (USD Render ROP, delegate `BRAY_HdKarmaXPU`).

## Conventions

- Renderer: Karma XPU only for now (no Arnold, no Nuke).
