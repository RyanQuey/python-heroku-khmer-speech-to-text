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
ot_or_nt=$2

# relative or abs path to src_dir
target_dir_name=with-metadata

# taken from this chart 
# https://versenotes.org/a-list-of-books-in-the-bible-by-number-of-chapters/
# english chapters
# for bash arrays: https://stackoverflow.com/a/8880633/6952495

declare -a chapters_per_book_ot=(
  "50"
  "40"
  "27"
  "36"
  "34"
  "24"
  "21"
  "4"
  "31"
  "24"
  "22"
  "25"
  "29"
  "36"
  "10"
  "13"
  "10"
  "42"
  "150"
  "31"
  "12"
  "8"
  "66"
  "52"
  "5"
  "48"
  "12"
  "14"
  "3"
  "9"
  "1"
  "4"
  "7"
  "3"
  "3"
  "3"
  "2"
  "14"
  "4"
)

declare -a chapters_per_book_nt=(
  "28"
  "16"
  "24"
  "21"
  "28"
  "16"
  "16"
  "13"
  "6"
  "6"
  "4"
  "4"
  "5"
  "3"
  "6"
  "4"
  "3"
  "1"
  "13"
  "5"
  "5"
  "3"
  "5"
  "1"
  "1"
  "1"
  "22"
)


if [ $# -lt 2 ]
  then
    echo "Need one args, like this:"
		echo "./copy-mp3-with-new-metadata-mp3-to-flac.sh ./Old\ Testament ot"
		echo "OR "
		echo "./copy-mp3-with-new-metadata.sh ./New\ Testament nt"
		exit 1
fi

# final slash matches only directories
# https://unix.stackexchange.com/a/86724/216300
# NOTE that this only works on KHOV style directory tree, e.g., 
# New Testament/01_matthew/01_matthew_01.mp3 etc.
for this_mp3_directory in $src_dir/*/ ; do
	echo "in dir: $this_mp3_directory"

	# make a subfolder in this dir for new files
	target_dir=$src_dir/$target_dir_name/$this_mp3_directory
	echo "making $target_dir..."

	# creating target dir if not exists
	mkdir -p $target_dir

	# https://stackoverflow.com/a/965072/6952495
	for filepath in $this_mp3_directory/*.mp3; do
		printf "\nfilepath: $filepath"
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
		re="^([0-9]{2})_([1-2]?-?)([a-zA-Z]+)_([0-9]{2,3}).mp3"
		# i.e,. for knowing what order this book is 
		if [[ $filename_with_ext =~ $re ]]; then
			full_match=${BASH_REMATCH}
			printf "\nfull match: $full_match\n"

			# also removing leading zeros https://stackoverflow.com/a/11130324/6952495
			book_num="$((10#${BASH_REMATCH[1]}))"
			book_series_num=${BASH_REMATCH[2]}
			book_name=${BASH_REMATCH[3]}
			chapter_num=${BASH_REMATCH[4]}

			# https://unix.stackexchange.com/a/93030/216300
			book_num_zero_index="$(($book_num-1))"
			printf "\nbook num  $book_num\n"

			if [ "$ot_or_nt" = "ot" ]; then
				chapters_for_this_book="${chapters_per_book_ot[$book_num_zero_index]}"
				book_num_in_bible=$book_num
			elif [ "$ot_or_nt" = "nt" ]; then
				chapters_for_this_book="${chapters_per_book_nt[$book_num_zero_index]}"
				book_num_in_bible="$(($book_num+39))"
			else
				echo "need to put either ot or nt for 2nd arg..."
				break
			fi
			# so it's properly alphabetical
			zero_padded_book_num=$(printf %02d $book_num_in_bible)

			printf "\nchapters for this book: $chapters_for_this_book\n"

			# https://stackoverflow.com/a/12487455/6952495
			# https://stackoverflow.com/a/13210909/6952495
			# capitalize (with caret) and replacement hyphens with space
			
			space=" "
			formatted_book_name="${book_series_num//[-]/$space}${book_name^}"
			# https://stackoverflow.com/a/11392248/6952495
			formatted_testament=${ot_or_nt^^}

			new_track_name="$formatted_book_name $chapter_num"
			new_album_name="KHOV - ${zero_padded_book_num} - ${formatted_book_name} (${formatted_testament})"

			echo "changing trackname to: ${new_track_name}"
			echo "changing album name to: ${new_album_name}"

			# track number
			# https://superuser.com/a/694884/654260
			# BEWARE -y forces overwrite
			# -n can be faster if don't need to overwrite
			#ffmpeg -n -loglevel quiet -i $filepath \
			ffmpeg -y -loglevel quiet -i $filepath \
				-metadata title="${new_track_name}" \
				-metadata album="${new_album_name}" \
				-metadata year=1954 \
				-metadata language=kh \
				-metadata track="${chapter_num}/${chapters_for_this_book}" \
				"$target_dir/${filename}.$extension"

		fi
		# can add break to test one chapter per book
		#break
	done
done

zip -r $target_dir.zip $target_dir
