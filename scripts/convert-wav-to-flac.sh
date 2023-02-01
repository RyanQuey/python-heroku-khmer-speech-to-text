#!/bin/bash

# takes a directory full of mp3s and converts to flac
# not recursive (though easily could be made to do so)

##################
# Instructions
# unzip first, e.g,. mkdir -p ./mp3s_dir && unzip files.zip -d ./mp3s_dir
# e.g., ./convert-mp3-to-flac.sh ./mp3s_dir ./flacs_dir

# relative or abs path to  where the mp3s live
src_dir=$1

# relative or abs path to where the flacs will live
target_dir=$2

if [ $# -lt 2 ]
  then
    echo "Need two args, like this:"
		echo "./convert-wav-to-flac.sh ./existing-wav_dir ./target-flacs_dir"
		exit 1
fi

# creating target dir if not exists
mkdir -p $target_dir

# https://stackoverflow.com/a/965072/6952495
for filepath in $src_dir/*.wav; do
	filename_with_ext=$(basename -- "$filepath")
	filename="${filename_with_ext%.*}"
	extension="${filename_with_ext##*.}"
	echo "========================="
	echo ""
	printf "\nfilename: $filename"
	printf "\nfilename_with_ext: $filename_with_ext"
	printf "\nextension: $extension"
	# mono channel, does not affect other settings
	ffmpeg -i "$filepath" -af aformat=channel_layouts=mono "$target_dir/${filename}.flac"
done

#zip -r $target_dir.zip $target_dir
