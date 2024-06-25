ffmpeg -i out_left.mov -i out_right.mov -filter_complex "[0:v][1:v]hstack=inputs=2" -c:v libx264 -crf 23 -preset fast output.mp4
