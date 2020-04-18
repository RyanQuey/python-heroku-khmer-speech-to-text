import os
import asyncio
from django.conf import settings
import firebase_admin
from firebase_admin import credentials
from firebase_admin import storage
from firebase_admin import firestore
from google.cloud import speech_v1p1beta1
from google.cloud.speech_v1p1beta1 import enums


from datetime import datetime
# experiment with logging
import traceback
import logging
import json

APP_NAME = "khmer-speech-to-text"
BUCKET_NAME = "khmer-speech-to-text.appspot.com"
logger = logging.getLogger('testlogger')
admin_key = os.environ.get('ADMIN_KEY_LOCATION')
no_role_key = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

# path to service account json file
service_account = admin_key or no_role_key
logger.info("which one is it??\n" + service_account)
cred = credentials.Certificate(service_account)
firebase_admin.initialize_app(cred, {
  'storageBucket': f'{BUCKET_NAME}'
})

# alias so don't have to write out the beta part
# for now only using the beta
speech = speech_v1p1beta1
speech_client = speech.SpeechClient.from_service_account_json(service_account)

bucket = storage.bucket()

cwd = os.getcwd()
destination_filename = cwd + "/tmp/"

WHITE_LISTED_USERS = [
	"rlquey2@gmail.com",
	"borachheang@gmail.com",
]

# note: not all flietypes supported yet. E.g., mp4 might end up being under flac or something. Eventually, handle all file types and either convert file or do something
FILE_TYPES = ["flac", "mp3", "wav"] 
file_types_sentence = ", ".join(FILE_TYPES[0:-1]) + ", and " + FILE_TYPES[-1]

# Setup firebase admin sdk
isDev = settings.ENV == "development"

# for Python, don't need to set the credentials, everything is automatically derived from system GOOGLE_APPLICATION_CREDENTIALS env var

db = firestore.Client()

base_config = {
	"encoding": enums.RecognitionConfig.AudioEncoding.LINEAR16,
	"language_code": 'km-KH',
	"sample_rate_hertz": None, # TODO or try 16000...but None let_s google set it themselves. For some mp3s, this returns no ut_terances or worse results though
	"enable_automatic_punctuation": True,
	"model": "default", #  Google: "Best for audio that is not one of the specific audio models. For example, long-form audio. Ideally the audio is high-fidelity, recorded at a 16khz or greater sampling rate."
	"max_alternatives": 3, # I think it's free, so why not get more ha
}

flac_config = {**base_config, 
	# or maybe FLAC ?
	"encoding": enums.RecognitionConfig.AudioEncoding.FLAC,
	"sample_rate_hertz": None, # NOTE one time, flac file (that was from mp4) had 44100 herz required, so bet_ter to just not set until can find out dynamically
}

mp3_config = {**base_config, 
	"encoding": enums.RecognitionConfig.AudioEncoding.MP3,
	"sample_rate_hertz": 16000,  # Google's docs say: "When using this encoding, sampleRateHertz has to match the sample rate of the file being used." TODO need to find a way to dynamically test the file to see it_s sample rate hertz
}

wav_config = {**base_config, 
	"encoding": None, # The FLAC and WAV audio file format_s include a header that describes the included audio content. You can request recognition for WAV files that contain either LINEAR16 or MULAW encoded audio. If you send FLAC or WAV audio file format in your request, you do not need to specify an AudioEncoding; the audio encoding format is determined from the file header. If you specify an AudioEncoding when you send send FLAC or WAV audio, the encoding configuration must match the encoding described in the audio header; otherwise the request returns an google.rpc.Code.INVALID_ARGUMENT error code.
	"sample_rate_hertz": None, # NOTE one time, flac file (that was from mp4) had 44100 herz required, so bet_ter to just not set until can find out dynamically
}

# returns the received request body and mutates request_options along the way 
# TODO request_options should be renamed to "request_dict"
# TODO make classes for the data object, maybe other objects as well. Set properties to it based on the data_dict used here. Then can access things via the properties, and it's more managable and usable throughout the request lifecycle
def setup_request(data, request_options):
    file_type = data["content_type"]
    request_options["file_type"] = file_type
    request_options["file_extension"] = file_type.replace("audio/", "")
    request_options[request_options["file_extension"]] = True
    
    if (request_options["file_extension"] not in FILE_TYPES):
        raise Exception( f'File type {request_options["file_extension"]} is not allowed, only {file_types_sentence}')
    
    # The audio file's encoding, sample rate in hertz, and BCP-47 language code
    # TODO set flac, mp3, or base64 dynamically de_pending on the file received (base64 encoding the file will set it with a header which states the file_type)
    if (data["file_path"]):
        # is in google cloud storage
        
        audio = {
                "uri": f"gs://khmer-speech-to-text.appspot.com/{data['file_path']}"
            }
        
        # if no data["file_path"], then there should just be base64
    else:
        # not really testing or using right now
        audio = {
                "content": data["base64"]
            }

    
    if (request_options["file_extension"] == "flac"):
        config_dict = flac_config
    
    elif (request_options["file_extension"] == "wav"):
        config_dict = wav_config
    
    elif (request_options["file_extension"] == "mp3"):
        # strangely enough, if send base64 of mp3 file, but use flac_config, returns results like the flac file, but smaller file size. In part, possibly due ot the fact that there is multiple speakers set for flacConfig currently
        config_dict = mp3_config
    
    else:
        # This is for other audio files...but not sure if we should support anything else
        config_dict = base_config

    
    # TODO dynamically test audio for channels
    if (request_options.get("multiple_channels")):
        config_dict["audio_channel_count"] = 2 # might try more later, but I think there's normally just two
        config_dict["enable_separate_recognition_per_channel"] = True
    
    # TODO not sure if we want to do it this way, but for now allowing user to be set like this
    # Security relies on the file being uploadable by the user, and keeping that secure, since if so we will only transcribe and then set transcriptions based on real files in the storage
    # user, which is needed to indicate who to snd transcript when we've finished. Only need uid though
    if not data.get("user", False):
        data["user"] = {"uid": data["file_path"].split("/")[1]}

    logger.info("sending file: " + data["filename"])
    # TODO consider sending their config object...though maybe has same results. But either way, check out the options in beta https://googleapis.dev/python/speech/latest/gapic/v1p1beta1/types.html#google.cloud.speech_v1p1beta1.types.RecognitionConfig
    logger.info("sending with config" + json.dumps(config_dict))
    
    request = {
        "audio": audio,
        "config": config_dict,
    }
    
    return request


def request_long_running_recognize(request, data, options = {}):
    try:
        user, filename, file_type, file_last_modified, file_size, file_path, original_file_path = [data.get(key) for key in ('user', 'filename', 'file_type', 'file_last_modified', 'file_size', 'file_path', 'original_file_path')]

        logger.info("options here is: " +  json.dumps(options))
        # this is initial response, not complete transcript yet
        operation_future = speech_client.long_running_recognize(request['config'], request['audio'])
        # NOTE for some reason operation_future.metadata returns None
        logger.info("operation name is: " + operation_future.operation.name)
        metadata = operation_future.operation
        transaction_name = metadata.name
        # TODO could add polling to operation in meantime and make it a cb instead, to send progress reports
        # https://google-cloud-python.readthedocs.io/en/0.32.0/core/operation.html
        # wait until complete and return
        result = operation_future.result()

        # Get a Promise re_presentation of the final result of the job
        # this part is async, will not return the final result, will just write it in the db
        # Otherwise, will timeout
        transcription_results = result.results
        # NOTE this might not be latest metadata, might be data from before it's finished. TODO try calling reload if it's not latest?
            
        handle_transcript_results(data, transcription_results, transaction_name)

    except Exception as error:
        logger.error(traceback.format_exc())

        # TODO or maybe try passing in details to the REtry arg?
        logger.error('Error while doing a long-running request:')
        logger.error(error)
        # TODO add back in maybe, but for now keep things simple
        if (options["failed_attempts"] < 2):
            # need at least two, one for if internal error, and then if another is for channels 
            options["failed_attempts"] += 1
            failures = options["failed_attempts"]

            # https://cloud.google.com/speech-to-text/docs/error-messages
            if (str(error) in [
                # got with fileout.wav. code 3 
                "Must use single channel (mono) audio, but WAV header indicates 2 channels.",  
                # got with fileout.flac 
                "400 Invalid audio channel count",
                ]):

                # try again with different channel configuration
                logger.info("trying again, but with multiple channel configuration.")
                options["multiple_channels"] = True
                logger.info(f'Attempt #: {failures + 1}')
                new_request = setup_request(data, options)
                request_long_running_recognize(new_request, data, options)

            elif ("13" in str(error)):
                # this is internal error Error while doing a long-running request: Error: 13 INTERNAL
                # not tested TODO

                logger.info("internal error, so just trying same thing again")
                logger.info(f"Attempt #: {failures + 1}")
                request_long_running_recognize(request, data, options)

            elif ("WAV header indicates an unsupported format." in str(error)):
                pass
                # TODO panic
                # not tested TODO

# maybe in future, store base64. Not necessary for now though, and we're billed by amount of data is stored here, so bet_ter not to. There's cheaper ways if we want to do this
def handle_transcript_results(data, results, transaction_name):
    # destructure data object
	# NOTE this should only have file_path if it was an uploads to storage (ie client didn't send base64)
    user, filename, file_type, file_last_modified, file_size, file_path, original_file_path = [data.get(key) for key in ('user', 'filename', 'file_type', 'file_last_modified', 'file_size', 'file_path', 'original_file_path')]

	# want sorted by filename so each file is easily grouped, but also timestamped so can support multiple uploads
    data["created_at"] = datetime.utcnow().strftime("%Y%m%dt%H%M%SZ")
	# array of objects with single key: "alternatives" which is array as well
	# need to convert to object_s or arrays only, can't do other custom types like "SpeechRecognitionResult"
    data["utterances"] = results # JSON.parse(JSON.stringify(results))
    data["transaction_id"] = transaction_name # best way to ensure a uid for this transcription

	# could also grab the name of the request (it_s a short-ish unique assigned by Google integer) if ever want to match this to the api call to google
    docName = f"{filename}-at-{data['created_at']}"
    doc_ref = db.collection('users').document(user["uid"]).collection("transcripts").document(docName)

	# set results into firestore
	# lodash stuff removes empty keys , which firestore refuses to store
    stripped_data = {k: v for k, v in data.items() if v is not None}

    logger.info("setting data to transcripts")
    doc_ref.set(stripped_data)

	# Some logger stuff
    logger.info("\n Transcript results: \n")
    logger.info(results)
    for result in results:
        # First alternative is the most probable result
        alternative = result.alternatives[0]
        logger.info(u"Transcript: {}".format(alternative.transcript))

	# cleanup storage and db records
	# TODO add error handling if fail to delete, so that it is marked as not deleted. Perhaps a separate try/catch so we know this is what fails, and not something after.
	# Or alternatively, something that tracks each ste_p and marks the last completed ste_p so we know where something stopped and can pick it up later/try again later
    if (file_path):
        # delete file from cloud storage (bucket assigned in the admin initializeApp call)
        storage_ref = admin.storage().bucket()

        logger.info("yes delete")
        storage_ref.file(file_path).delete()

    if (original_file_path):
        # delete file from cloud storage (bucket assigned in the admin initializeApp call)
        storage_ref = admin.storage().bucket()

        logger.info("yes delete original too")
        storage_ref.file(original_file_path).delete()

        # mark upload as finished transcribing
        untranscribed_uploads_ref = db.collection('users').document(user["uid"]).collection("untranscribedUploads")
        response = untranscribed_uploads_ref.delete()

def handleDbError(err):
	# see ht_tps://stackoverflow.com/questions/52207155/firestore-admin-in-node-js-missing-or-insufficient-permissions
    if (err["message"].includes("PERMISSION_DENIED: Missing or insufficient permissions")):
        logger.info("NOTE: check to make sure service account key put into 'admin.credential.cert(serviceAccount)' has firebase-adminsdk role")

    logger.info("Error hitting firestore DB: ", err)

# based on ht_tps://github.com/firebase/functions-samples/blob/master/ffmpeg-convert-audio/functions/index.js
# TODO might be bet_ter in the future, for more flexibility and ease of use, to just use ffmpeg-static and bash code rather than a wrapper, so can write exactly as it would be in the command line
def makeItFlac(data, options = {}):
    pass

"""
	try {
	  {filename, file_type, file_path } = data

		  # if (file_type !== "audio/flac") {
		  if (file_type !== "video/mp4") {
	    # only converting mp4's right now, but just change this and you can
		    logger.info('not converting to a flac.')
		    return null
		  }
	  logger.info("flacify it", filename)
		  
		  # Download file from bucket.
		  //bucket = gcs.bucket(fileBucket)
	  bucket = admin.storage().bucket()
		  temp_file_path = path.join(os.tmpdir(), filename)
		  # We add a '_output.flac' suffix to target audio file name. That's where we'll upload the converted audio.
		  target_temp_filename = filename.replace(/\.[^/.]+$/, '') + '_output.flac'
		  target_temp_file_path = path.join(os.tmpdir(), target_temp_filename)
		  target_storage_file_path = path.join(path.dirname(file_path), target_temp_filename)
		  
		  bucket.file(file_path).download({destination: temp_file_path})
		  logger.info('Audio downloaded locally to', temp_file_path)
		  # Convert the audio to mono channel using FFMPEG.
		  
		  let command = ffmpeg(temp_file_path)
		    .setFfmpegPath(ffmpeg_static)
		    .output(target_temp_file_path)

	  if (file_type.includes("video/mp4")) {
	    # equivalent of doing -vn flag
	    command = command
	      .withNoVideo()
	      .audioCodec('flac') # equivalent of doing -acodec copy

	  else:
	    # changing audio file to flac
		    command = command.format('flac')

	    if (options["force_single_channel"]) {
	      # TODO untested
		      command = command
	          .audioChannels(1)
		        .audioFrequency(16000) # not sure if necessary for anything, much less single channel, but google used in their example
	    }
	  }

		  Helpers.promisifyCommand(command)
		  logger.info('Output audio created at', target_temp_file_path)

	  bucket.upload(target_temp_file_path, {destination: target_storage_file_path})
	  logger.info('Output audio uploaded to', target_storage_file_path)
		  
		  # Once the audio has been uploaded delete the local file to free up disk space.
		  fs.unlinkSync(temp_file_path)
		  fs.unlinkSync(target_temp_file_path)

	  data["converted_filename"] = target_temp_fileName
	  data["original_file_type"] = file_type
	  data["file_type"] = "audio/flac"
	  # need both file_path and original file path since need to delete both once we're done
	  data["original_file_path"] = file_path
	  data["file_path"] = target_storage_file_path

	  return
	} catch (error) {
	  # 
	  logger.info("Error flacifying file: " + error)
	  logger.info("just try it without flacifying")

"""

# maybe use later
def download_file(source_filename): 
    blob = bucket.blob(source_filename)
    # blob.download_to_filename(destination_filename)

    logger.info(
        "Blob {} downloaded to {}.".format(
            source_filename, destination_filename
        )
    )
    logger.info(f'blob here: {blob}')
  # file_path = object["name"]; # File path in the bucket.
  # content_type = object["content_type"]
  # filename = path["basename"](file_path)

  # # Exit if this is triggered on a file that is not an image.
  # if (!content_type.startsWith('audio/') && !content_type == 'video/mp4') {
  #   return logger.info('This is not an audio file or mp4.')
  # }
  # 
  # data = {
  #   # google storage path
  #   file_path, 
  #   # various metadata
  #   file_type: content_type,
  #   filename,
  #   file_last_modified: object["metadata"]["file_last_modified"], 
  #   file_size: object["size"],
  #   file_type: content_type, 
  #   # user, which is needed to indicate who to snd transcript when we've finished. Only need uid though
  #   user: {uid: file_path.split("/")[1]} # from "audio/{uid}/{myfile.flac}"
  # }

  # main(data).catch((error) => {
  #   logger.info("Error while requesting transcript for audio file in storage hook: ", error)
  #   return
  # })

  # return "great job"

def poll_operation(operation_future):
    """
    takes google operation future and keeps polling it until complete
    """
    
