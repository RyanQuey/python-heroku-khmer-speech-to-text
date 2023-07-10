#!/bin/bash

# takes a directory full of mp3s and changes metadata based on filename
# - recursive 
# - source: https://stackoverflow.com/a/11479066/6952495
# this file specifically designed for KHOV mp3 files, but can be easily adjusted for other use cases

##################
# Instructions
# unzip first, e.g,. mkdir -p ./mp3s_dir && unzip files.zip -d ./mp3s_dir
# e.g., ./convert-mp3-to-flac.sh ./mp3s_dir ./flacs_dir

# relative or abs path to  where the mp3s live
src_dir=$1

# relative or abs path to where the flacs will live
target_dir_name=with-metadata

if [ $# -lt 2 ]
  then
    echo "Need two args, like this:"
		echo "./convert-mp3-to-flac.sh ./existing-mp3s_dir ./target-flacs_dir"
		exit 1
fi

# final slash matches only directories
# https://unix.stackexchange.com/a/86724/216300
for this_mp3_directory in $src/*/ ; do
	echo "$d"

	# make a subfolder in this dir for new files
	target_dir=$this_mp3_directory/$target_dir_name

	# creating target dir if not exists
	mkdir -p $target_dir

	# https://stackoverflow.com/a/965072/6952495
	for filepath in $this_mp3_directory/*.mp3; do
		filename_with_ext=$(basename -- "$filepath")
		filename="${filename_with_ext%.*}"
		extension="${filename_with_ext##*.}"

    # - source: https://stackoverflow.com/a/11479066/6952495
		echo "========================="
		echo ""
		# e.g., 01_genesis_001.mp3
		printf "\nfilename: $filename"
		printf "\nfilename_with_ext: $filename_with_ext"
		printf "\nextension: $extension"

		# https://stackoverflow.com/a/19737726/6952495
		re="^([0-9]{2})_([1-2]?-?[a-zA-Z]+)_([0-9]{3}).mp3"
		# i.e,. for knowing what order this book is 
		full_match=${BASH_REMATCH}
		book_num=${BASH_REMATCH[1]}
		book_name=${BASH_REMATCH[2]}
		chapter_num=${BASH_REMATCH[3]}

		new_track_name="$book_name $chapter_num"
		new_album_name=$book_name

		echo "changing trackname to:"
		printf 

		ffmpeg -loglevel quiet -i $filepath -codec copy -metadata \
			title="My title" \
			$filepath


		# -ac 1 for mono channel
		ffmpeg -i "$filepath" -ac 1 "$target_dir/${filename}.flac"
	done
done

zip -r $target_dir.zip $target_dir
