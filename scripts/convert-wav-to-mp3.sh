#!/bin/bash

# takes a directory full of mp3s and converts to flac
# not recursive (though easily could be made to do so)

##################
# Instructions

# relative or abs path to  where the mp3s live
src_dir=$1

# relative or abs path to where the flacs will live
target_dir=$2

if [ $# -lt 2 ]
  then
		echo "Need two args, like this: (though can send to same dir)"
		echo "./convert-wav-to-mp3.sh ./existing-wav_dir ./target-mp3s_dir"
		exit 1
fi

# creating target dir if not exists
mkdir -p $target_dir

# https://stackoverflow.com/a/12952172/6952495
for filepath in $src_dir/*.wav; do
	filename_with_ext=$(basename -- "$filepath")
	filename="${filename_with_ext%.*}"
	extension="${filename_with_ext##*.}"
	echo "========================="
	echo ""

	# check if target exists already, and if so can just skip
	# NOTE sometimes you want to overwrite, if so can just comment out these lines
	if test -f "$target_dir/${filename}.mp3"; then
		echo "file already exists at $target_dir/${filename}.mp3, skipping"
		continue
	fi




	printf "\nfilename: $filename"
	printf "\nfilename_with_ext: $filename_with_ext"
	printf "\nextension: $extension"
	# mono channel, does not affect other settings

	ffmpeg -i "$filepath"  -vn -ac 1 -b:a 128k "$target_dir/${filename}.mp3"
done

#zip -r $target_dir.zip $target_dir
