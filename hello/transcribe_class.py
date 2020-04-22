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
from copy import deepcopy

# TODO get all these constants to somewhere else and import them
# probably grab some of the class vars too eg _base_config
APP_NAME = "khmer-speech-to-text"
BUCKET_NAME = "khmer-speech-to-text.appspot.com"
logger = logging.getLogger('testlogger')
admin_key = os.environ.get('ADMIN_KEY_LOCATION')
no_role_key = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

# path to service account json file
# don't need to set the credentials, everything is automatically derived from system GOOGLE_APPLICATION_CREDENTIALS env var. But if need a different credential, can set it 
service_account = admin_key or no_role_key
cred = credentials.Certificate(service_account)
firebase_admin.initialize_app(cred, {
    'storageBucket': BUCKET_NAME,
    'projectId': APP_NAME,
    'databaseURL': f"https://{APP_NAME}.firebaseio.com/",
})

# not sure why, but doing admin.firestore.Client() doesn't work on its own
db = firestore.Client.from_service_account_json(service_account)

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
# mpeg is often mp3
FILE_TYPES = ["flac", "mp3", "wav", "mpeg"] 
file_types_sentence = ", ".join(FILE_TYPES[0:-1]) + ", and " + FILE_TYPES[-1]

# Setup firebase admin sdk
isDev = settings.ENV == "DEVELOPMENT"

REQUEST_TYPES = [
    "initial-request", 
    "continue-transcribing-request",
]

APIS = ["v1", "v1p1beta"]
BASE_REQUEST_OPTIONS = {
  # maybe better to ask users to stop doing multiple channels, unless it actually helps
  "multiple_channels": False, 
  "api": APIS[1],
  "failed_attempts": 0, # TODO move to diff dict, since it's not an option
}

TRANSCRIPTION_STATUSES = [
    # 0 
    # the first stage, before this no reason to bother even recording
    # client sets
    "uploading",

    # 1
    # finished upload
    # client sets
    "uploaded",

    # 2
    # when request has been received and accepted by our server, and is processing the file
    # server sets
    "received-by-server", 

    # 3
    # when Google has started the operation to transcribe the file, and is currently transcribing.   
    # server sets
    "transcribing", 

    # 4
    # Google finished transcribing, but we haven't yet processed their transcription for whatever reason
    "transcription-complete",

    # 5
    # we finished processing their transcription, and it is stored in firestore
    # actually were not really persisting when it gets here, just deleting the transcribe request record
    "transcription-processed",

    # 6
    # when request had been received and accepted by our server, but then we errored before beginning the translation through google
    # server sets
    "server-error", 

    # 7
    # when Google had started the operation to transcribe the file, but then Google had some sort of error
    # client sets or server sets (if server had crashed and didn't get a chance to set it by itself)
    "transcribing-error", 

]




class TranscribeRequest:
    """
    Handle the lifecycle of a request to transcribe an audio file into text

    # 1) receive filename and filemodified and user
    # 2) use that to check fire store for the latest data
    # 3) use data from Firestone or to set the other attributes
    """

    def __init__(self, file_data):
        # necessary parts, or else can't retrieve from db
        # TODO if don't receive, throw error so that client knows
        self._set_attributes_from_dictionary(file_data)

    ########################
    # init helpers
    ########################
    def _set_attributes_from_dictionary(self, file_data):
        """
        file_data should be dictionary with file data
        called initially, but also when refreshing data based on the database
        """

        self.filename = file_data["filename"]
        self.file_last_modified = file_data["file_last_modified"]

        # optional data from payload 
        # TODO test how optional all of this is
        # either user and/or user_id or file_path need to be set
        self.request_type = file_data.get("request_type", REQUEST_TYPES[0])
        self.user = file_data.get("user", {"uid": file_data["user_id"]})
        self.file_path = file_data.get("file_path")
        self.file_type = file_data.get("content_type")
        # NOTE some filetypes, such as some mp3s, are different from the file extension, e.g., mpeg instead of mp3
        self.file_extension = self.file_type.replace("audio/", "")
        self.file_size = file_data.get("file_size")
        self.original_file_path = file_data.get("original_file_path") 
        self.status = None # get when retrieve record from firestore
        # only counting attempts in this current http request, so always set to 0
        self.failed_attempts = 0
        # received from google when started already
        self.transaction_id = file_data.get("file_path")
        self._set_request_options()

    def _set_request_options(self, **kwargs):
        self.request_options = deepcopy(BASE_REQUEST_OPTIONS)
        self.request_options[self.file_extension] = True

    #######################
    # getters/getter helpers
    ########################

    def attempt_count(self):
        return self.failed_attempts + 1

    def transcripts_for_file_identifier(self):
        """
        is not a uuid, but is based on the file, so that one file keeps all of its transcripts together
        """
        stripped_filename = self.filename.replace(".", "")
        identifier = f"{stripped_filename}-lastModified{self.file_last_modified}"
        return identifier

    def transcript_document_name(self):
        return f"{self.filename}-at-{self.transcript_created_at}"

    def user_ref(self):
        return db.collection('users').document(self.user["uid"])

    def transcript_document_ref(self):
        doc_name = self.transcript_document_name()
        return self.user_ref().collection("transcripts").document(doc_name)

    def transcribe_request_ref(self):
        identifier = self.transcripts_for_file_identifier()
        return self.user_ref().collection("transcribeRequests").document(identifier)

    def _get_errored_while(self):
        """
        returns string with last non-error status
        only necessary when there's a new error; otherwise can just check self.errored_while attr


        """
        if "error" in self.status:
            # just return the last thing, which should not be an error (errored_while should never be error)
            return self.errored_while
        else:
            return self.status

    ##################################################
    # helpers for interacting with Google Speech API 
    ################################################

    def setup_request(self):
        """
        build a config_dict and audio dict to send to Google
        """

        try:
            if (self.file_extension not in FILE_TYPES):
                raise Exception( f'File type {self.file_extension} is not allowed, only {file_types_sentence}')
            
            # The audio file's encoding, sample rate in hertz, and BCP-47 language code
            if (self.file_path):
                # is in google cloud storage
                
                audio = {
                    "uri": f"gs://khmer-speech-to-text.appspot.com/{self.file_path}"
                }
                
                # if no data["file_path"], then there should just be base64
            else:
                # not really testing or using right now
                audio = {
                    "content": self.base64
                }

            
            if (self.file_extension == "flac"):
                config_dict = TranscribeRequest._flac_config
            
            elif (self.file_extension == "wav"):
                config_dict = TranscribeRequest._wav_config
            
            elif (self.file_extension in ["mp3", "mpeg"]):
                # strangely enough, if send base64 of mp3 file, but use flac_config, returns results like the flac file, but smaller file size. In part, possibly due ot the fact that there is multiple speakers set for flacConfig currently
                config_dict = TranscribeRequest._mp3_config
            
            else:
                # This is for other audio files...but not sure if we should support anything else
                config_dict = TranscribeRequest._base_config

            
            # TODO dynamically test audio for channels
            if (self.request_options.get("multiple_channels")):
                config_dict["audio_channel_count"] = 2 # might try more later, but I think there's normally just two
                config_dict["enable_separate_recognition_per_channel"] = True
            
            # TODO not sure if we want to do it this way, but for now allowing user to be set like this
            # Security relies on the file being uploadable by the user, and keeping that secure, since if so we will only transcribe and then set transcriptions based on real files in the storage
            # user, which is needed to indicate who to snd transcript when we've finished. Only need uid though
            if not self.get("user", False):
                self.user = {"uid": self.file_path.split("/")[1]}

            logger.info("sending file: " + self.filename)
            # TODO consider sending their config object...though maybe has same results. But either way, check out the options in beta https://googleapis.dev/python/speech/latest/gapic/v1p1beta1/types.html#google.cloud.speech_v1p1beta1.types.RecognitionConfig
            logger.info("sending with config" + json.dumps(config_dict))
            
            requestParams = {
                "audio": audio,
                "config": config_dict,
            }

            self.requestParams = requestParams

        except Exception as error:
            # mark request status in firestore 
            self.mark_as_server_error(error)


    # for when status "received_by_server" 
    # TODO if "server-error", have server check things and make sure it's a kind of error that we want to retry, or if not, make the necessary changes before trying again.
    def request_long_running_recognize(self):
        logger.info("----------------------------------------------------------------")
        logger.info("----------------------------------------------------------------")
        try:
            logger.info(f"Attempt # {self.attempt_count()}")

            logger.info("options here is: " +  json.dumps(self.request_options))
            # this is initial response, not complete transcript yet
            # TODO handle if there's no file there, ie it got deleted but they request again or something
            operation_future = speech_client.long_running_recognize(self.request_params['config'], self.request_params['audio'])
            # NOTE for some reason operation_future.metadata returns None
            self.mark_as_transcribing(operation_future)

        except Exception as error:
            logger.error(traceback.format_exc())

            # TODO or maybe try passing in details to the REtry arg?
            logger.error('Error while doing a long-running request:')
            logger.error(error)
            # TODO add back in maybe, but for now keep things simple
            if (self.failed_attempts < 3):
                # need at least two, one for if internal error, and then if another is for channels 
                self.failed_attempts += 1

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

                    self.request_option["multiple_channels"] = True
                    self.setup_request()
                    self.request_long_running_recognize()

                elif ("13" in str(error)):
                    # this is internal error Error while doing a long-running request: Error: 13 INTERNAL
                    # not tested TODO

                    logger.info("internal error, so just trying same thing again")
                    self.request_long_running_recognize()

                elif ("WAV header indicates an unsupported format." in str(error)):
                    pass
                    # TODO panic
                    # not tested TODO

            else:
                # TODO mark as either server error or Google error depending on the error  
                self.mark_as_server_error(error)


    def check_request_transcribe_status(self):
        pass

    # TODO remane "process transcript results"
    def handle_transcript_results(self, results):
        """
        takes completed transcript results and processes it
        maybe in future, store base64. Not necessary for now though, and we're billed by amount of data is stored here, so bet_ter not to. There's cheaper ways if we want to do this

        """


        # NOTE this should only have file_path if it was an uploads to storage (ie client didn't send base64)

        # prepare to send to firestore
        # want sorted by filename so each file is easily grouped, but also timestamped so can support multiple uploads
        # also want it to be easily placeable in a url without any difficulty
        # TODO put in function that first finds out that Google speech api is finished
        self.transcript_created_at = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        # array of objects with single key: "alternatives" which is array as well
        # need to convert to objects or arrays only, can't do other custom types like "SpeechRecognitionResult"

        # could also grab the name of the request (it_s a short-ish unique assigned by Google integer) if ever want to match this to the api call to google
        data = self.__dict__

        mapped_results = []
        for result in results:
            result_dict = {
                "channel_tag": result.channel_tag,
                "language_code": result.language_code,
                "alternatives": [],
            }

            result_dict["alternatives"] = []
            #     logger.info("looking at result: " + str(i_r))
                            
            for alt in result.alternatives:
                alt_dict = {
                    "transcript": u"{}".format(alt.transcript), 
                    "confidence": alt.confidence
                }
                logger.info(alt_dict)
                result_dict["alternatives"].append(alt_dict)

            mapped_results.append(result_dict)

        data["utterances"] = mapped_results
        logger.info("setting data to transcripts")


        self.persist_transcript_data(data)

        # Some logger stuff
        logger.info("\n Transcript results: \n")
        for result in results:
            # First alternative is the most probable result
            alternative = result.alternatives[0]
            logger.info(u"Transcript for this result: {}".format(alt.transcript))

            # cleanup storage and db records
            # TODO add error handling if fail to delete, so that it is marked as not deleted. Perhaps a separate try/catch so we know this is what fails, and not something after.
            # Or alternatively, something that tracks each ste_p and marks the last completed ste_p so we know where something stopped and can pick it up later/try again later

        # TODO put in separate method
        for path in [file_path, original_file_path]:
            if (path):
                # delete file from cloud storage (bucket assigned in the admin initializeApp call)

                logger.info("deleting file from " + path)
                bucket.blob(path).delete()
                logger.info("deleted file from " + path)

        # mark upload as finished transcribing



    def poll_operation(self, operation_future):
        """
        takes google operation future and keeps polling it until complete
        """


    ##############################
    # File manipulation methods
    ##########################
    def makeItFlac(self, data, options = {}):
        """
        converts file (eg mp3, wav, mp4) to flac file
        based on ht_tps://github.com/firebase/functions-samples/blob/master/ffmpeg-convert-audio/functions/index.js
        TODO might be bet_ter in the future, for more flexibility and ease of use, to just use ffmpeg-static and bash code rather than a wrapper, so can write exactly as it would be in the command line
        """
        pass


    # maybe use later
    def download_file(self, source_filename): 
        blob = bucket.blob(source_filename)
        # blob.download_to_filename(destination_filename)

        logger.info(
            "Blob {} downloaded to {}.".format(
                source_filename, destination_filename
            )
        )
        logger.info(f'blob here: {blob}')

    ################################
    # top level helpers for firestore
    ################################

    def refresh_from_db(self):
        """ 
        ultimately db should be source of truth, so occassionally need to pull directly from there
        """
        ref = self.transcribe_request_ref()
        transcribe_request_doc = ref.get()

        if transcribe_request_doc.exists:
            # TODO remove this later, just for now as we're actively developing this method
            logger.info("Transcribe Request record found: ")
            file_data = transcribe_request_doc.to_dict()
            logger.info(file_data)

            # set to this class instance
            self._set_attributes_from_dictionary(file_data)

        else:
            logger.info("Uh oh...no transcribe Request record found...")
            # TODO handle, this means we need to request transcript again


    def persist_transcript_data(self, data):
        """
        data is dictionary, based on Transcribe class instance
        sets data to the transcript ref in firestore
        only for completed transcripts (incomplete should be at transcribeRequests ref)
        doc_name is unique identifier for this transcription, different for each version of the transcript even for the same file
        """
        cleaned_data = TranscribeRequest.cleanup_dictionary(data)
        doc_ref = self.transcript_document_ref()
        doc_ref.set(cleaned_data)

    #############################
    # status marking methods (for persisting in firestore)
    #############################
    def mark_as_received(self):
        self._update_status(TRANSCRIPTION_STATUSES[2]) # received-by-server
        pass

    def mark_as_transcribing(self, operation_future):
        """
        operation_future is an operation_future received from Google in response to hitting their speech to text api
        """

        logger.info("operation name is: " + operation_future.operation.name)
        metadata = operation_future.operation
        self.transaction_id = metadata.name

        # https://google-cloud-python.readthedocs.io/en/0.32.0/core/operation.html
        self._update_status(TRANSCRIPTION_STATUSES[3], { # transcribing
            "transaction_id": self.transaction_id,
        }) 
        pass

    def mark_as_transcribed(self):
        self._update_status(TRANSCRIPTION_STATUSES[4]) # transcription-complete
        pass

    def mark_as_processed(self):
        """
        delete the record, now should have a transcript already so no need for this
        """

        logger.info("deleting record of untranscribed upload: " + f"users/{self.user['uid']}/transcribeRequests/{identifier}")

        transcribe_request_ref = self.transcribe_request_ref()

        # delete it, since we're all done
        response = transcribe_request_ref.delete()
        logger.info("deleted record of untranscribed upload...since it's uploaded")
        logger.info(response)

    def mark_as_server_error(self, error):
        logger.error("Marking as Server error")
        logger.error(error)
        self.errored_while = self._get_errored_while()
        self._update_status(TRANSCRIPTION_STATUSES[6], other={
            "error": str(error),
            "errored_while": self.errored_while,
        }) # server-error 
        pass

    # keep separate from server error for now, I think they are different enough that we want to handle differently more and more as this server is built out
    def mark_as_transcribing_error(self, error):
        logger.error(error)
        self.errored_while = self._get_errored_while()
        self._update_status(TRANSCRIPTION_STATUSES[7], other={
            "error": str(error),
            "errored_while": self.errored_while,
        }) # transcribing-error 
        pass

    def _update_status(self, status, **kwargs):
        other = kwargs.get("other", {})
        """
        set the status without overwriting anything else
        """
        if other == None:
            other = {}

        # update self
        self.status = status
        updates = {
            **other, 
            "status": status,
            "updated_at": datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"),
        }

        # update firestore
        transcribe_request_ref = self.transcribe_request_ref()
        transcribe_request_ref.set(updates, merge=True)



    ################################    
    # class variables
    ################################
    # encoding: 
    # - Google: "The FLAC and WAV audio file format_s include a header that describes the included audio content. You can request recognition for WAV files that contain either LINEAR16 or MULAW encoded audio. If you send FLAC or WAV audio file format in your request, you do not need to specify an AudioEncoding; the audio encoding format is determined from the file header. If you specify an AudioEncoding when you send send FLAC or WAV audio, the encoding configuration must match the encoding described in the audio header; otherwise the request returns an google.rpc.Code.INVALID_ARGUMENT error code."

    # sample rate hertz:  
    # - None lets google set it themselves. 
    # - For some mp3s, this returns no utterances or worse results though
    # - Regarding MP3s, Google's docs say: "When using this encoding, sampleRateHertz has to match the sample rate of the file being used." TODO need to find a way to dynamically test the file to see it_s sample rate hertz

    # model:  
    # - Google: "Best for audio that is not one of the specific audio models. For example, long-form audio. Ideally the audio is high-fidelity, recorded at a 16khz or greater sampling rate."

    _base_config = {
        "encoding": enums.RecognitionConfig.AudioEncoding.LINEAR16,
        "language_code": 'km-KH',
        "sample_rate_hertz": None, 
        "enable_automatic_punctuation": True,
        "model": "default", 
        "max_alternatives": 3, # I think it's free, so why not get more ha
    }

    _flac_config = {
        **_base_config, 
        # or maybe FLAC ?
        "encoding": enums.RecognitionConfig.AudioEncoding.FLAC,
        "sample_rate_hertz": None, 
    }

    _mp3_config = {
         **_base_config, 
         "encoding": enums.RecognitionConfig.AudioEncoding.MP3,
         "sample_rate_hertz": 16000,  
    }

    _wav_config = {
         **_base_config, 
         "encoding": None, 
         "sample_rate_hertz": None, 
    }


    ####################
    # class/static methods
    ###################
    @staticmethod
    def cleanup_dictionary(data):
        """
        takes a dictionary and removes all empty keys, so can be persisted by firestore
        """
        cleaned_data = {}
        for k, v in data.items():
            # don't set any empty values, since firestore doesn't like it
            if v is not None:
                cleaned_data[k] = v

        return cleaned_data

