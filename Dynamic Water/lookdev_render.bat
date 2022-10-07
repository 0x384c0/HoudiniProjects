ffmpeg -framerate 24 -y -gamma 2.2 -layer beauty_nwm  -i "render/dynamic_water.Redshift_ROP1.%%04d.exr" "render\look_dev.mp4"
:: pause