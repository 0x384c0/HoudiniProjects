ffmpeg -framerate 24 -y -i "render/flipbook.%%d.jpg" "nuke_nc\render\flipbook.mp4"
ffplay "nuke_nc\render\flipbook.mp4"
:: pause