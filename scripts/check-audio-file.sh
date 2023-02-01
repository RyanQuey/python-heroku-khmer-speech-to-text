#!/bin/bash

# takes a directory full of mp3s and converts to flac
# not recursive (though easily could be made to do so)

##################
# Instructions
# e.g., ./check-audio-file.sh ./mp3s_dir/my-file.mp3

# relative or abs path to  where the mp3s live
target_file=$1

# makes it so `ffprobe` command handles the spaces in folder and file names
IFS=$'\n'

ffprobe -i $target_file  -show_streams -select_streams a:0 | grep channel
