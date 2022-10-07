ffmpeg -framerate 24 -y -gamma 2.2 -layer beauty_nwm  -i "render/Seirai.Redshift_ROP_look_dev.%%04d.exr" "nuke_nc\render\look_dev.mp4"
:: pause