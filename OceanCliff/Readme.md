Requirements
* Houdini 20.5
* [bridge](https://quixel.com/bridge)
* Nuke 15
* ffmpeg
* [virtuallens](https://www.nukepedia.com/gizmos/filter/virtuallens), [expoglow](https://www.nukepedia.com/gizmos/filter/expoglow), [wptk](https://www.nukepedia.com/toolsets/3d/wptk)

Render
* download bridge assets: scatter_misc_siqa2bo, Nature_Rock_uk5ofde, nature_rock_uk5pdhh, Nature_Rock_uk5pebv, Nature_Rock_uk5oded, 3d_rock_tetebdvda, 3d_rock_siCs3, Nature_Rock_vceldhvfa, 3d_rock_slnv6, Nature_Rock_ulfucbn, Nature_Rock_ulbrbdt, rock_jagged_ulmiccava, 3d_nature_vi5qfiq, 3d_rock_sjbrG, Nature_Rock_veflbabqx, nature_rock_yfxici3ab, nature_rock_xgnlfc0, 3d_nature_yg1laj2qx, nature_rock_weiqaahfa, nature_rock_wdrhegb, nature_rock_vivvaewaw, nature_rock_wfeqcgdbw, nature_rock_wfkiddlva, nature_rock_wemraic, nature_rock_weoochx, nature_rock_wftnffyva
* install [lop_megascans_3d_asset.hda](/R&D/megascans/hda/lop_megascans_3d_asset.hda)
* open .hip project
* In "Aliases and vaairables" set `HIP_CACHE` and `MEGASCANS_DOWNLOADED`
* cook `/tasks/topnet1/output0`
* open [nuke/ocean_cliff.nknc](nuke/ocean_cliff.nknc)
* press "Render all writes" in node "render_all_writes"
* press "Merge tiles" in node "merge_tiles"