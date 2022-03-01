from .helpers import * 
logger = logging.getLogger('testlogger')

class TranscribeRequest:
    """
    Handle the lifecycle of a request to transcribe an audio file into text

    # 1) receive filename and filemodified and user
    # 2) use that to check fire store for the latest data
    # 3) use data from Firestone or to set the other attributes
    """

    # a dict of custom quotas for this user, if defaults have been overridden
    custom_quotas = None
    user_email = None

    # TODO NOTE no longer file_data, so change var name
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

        If there is an error, need to account for the errored_while when running stats. So if errored while transcribing, count from 
        If there are multiple errors, throw out from stats altogether
        """

        self.filename = file_data["filename"]
        self.file_last_modified = file_data["file_last_modified"]
        self.id = file_data["id"]

        # optional data from payload 
        # TODO test how optional all of this is
        # TODO DRY up using setattr and some sort of schema dict
        self.request_type = file_data.get("request_type", REQUEST_TYPES[0])
        self.user_id = file_data.get("user_id")
        self.file_path = file_data.get("file_path")
        self.file_type = file_data.get("file_type")
        # NOTE some filetypes, such as some mp3s, are different from the file extension, e.g., mpeg instead of mp3
        self.file_extension = self.file_type.replace("audio/", "")
        self.file_size = file_data.get("file_size")
        self.original_file_path = file_data.get("original_file_path") 
        self.transaction_id = file_data.get("transaction_id")
        self.event_logs = self.get_event_logs()
        self.status = file_data.get("status")
        self.updated_at = file_data.get("updated_at")

        # only counting attempts in this current http request, so always set to 0
        self.failed_attempts = 0
        # received from google when started already
        self._set_request_options()

    def _set_request_options(self, **kwargs):
        self.request_options = deepcopy(BASE_REQUEST_OPTIONS)
        self.request_options[self.file_extension] = True


    #######################
    # getters/translators for getters
    ########################

    def attempt_count(self):
        return self.failed_attempts + 1

    def transaction_complete(self):
        return self.status == TRANSCRIPTION_STATUSES[5]

    def transcripts_for_file_identifier(self):
        """
        is not a uuid, but is based on the file, so that one file keeps all of its transcripts together
        """
        stripped_filename = self.filename.replace(".", "")
        identifier = f"{stripped_filename}-lastModified{self.file_last_modified}"
        return identifier

    # not really used by anything, so just make sure it's unique. I don't even think you can sort by it very easily
    def transcript_document_name(self):
        return f"{self.filename}-at-{self.transaction_id}"

    def user_ref(self):
        return db.collection('users').document(self.user_id)

    def get_user_email(self):
        """
        get from db or from cache
        - all users should have an email, so there should be no concern about retriving email from this record in firestore
        """
        if self.user_email == None:
            self.user_email = self.user_ref().get().to_dict()["email"]

        return self.user_email

    def get_max_size_mb(self):
        """
        returns int of max file size in MB for user
        - might hit firebase db depending on if get_custom_quotas has been called before or not
        """
        default_file_size_limit = 50 # 50 MB is pretty large, perhaps around 10 minutes of audio for a flac file

        # converting to float in case it's accidentally stored as string
        file_size_limit = float(self.get_custom_quotas().get("audioFileSizeMB", default_file_size_limit))

        logger.info(f"user file size limit: {file_size_limit}")

        return file_size_limit

    def get_custom_quotas(self):
        """
        get from db or from cache
        - returns empty dict if there are no custom quotas set for this user
        """
        if self.custom_quotas == None:
            email = self.get_user_email()
            logger.info(f"checking firestore at customQuotas/{email}")
            custom_quotas_result = db.collection('customQuotas').document(email).get()
            self.custom_quotas = custom_quotas_result.to_dict() if custom_quotas_result.exists else {}


        logger.info(f"custom quotas dict: {self.custom_quotas}")
        return self.custom_quotas

    def transcript_document_ref(self):
        doc_name = self.transcript_document_name()
        return self.user_ref().collection("transcripts").document(doc_name)

    def transcribe_request_ref(self):
        return self.user_ref().collection("transcribeRequests").document(self.id)

    def size_in_MB(self):
        return float(self.file_size) / 1048576

    def elapsed_since_last_event(self):
        status = self.status

        # remove letters so can compare just the numbers
        remove_letters = str.maketrans({"T": "", "Z": ""})

        now = int(timestamp().translate(remove_letters))
        last_updated_at = int(self.updated_at.translate(remove_letters))
        # is kind of difference in seconds, unless we go above 60. Then it gets confusing (e.g., 300 would be 3 minutes, 3000 would be 30 minutes, 30000 would be 3 hours etc)
        elapsed_time = now - last_updated_at

        return elapsed_time

    ##################
    # Validation
    ##################

    def validate_request(self):
        """
        check to see if audio file is valid before sending anything to Google
        - check file size to make sure that it is under 100 MB or custom limit
        - maybe add other requirements later
        """
        max_size = self.get_max_size_mb()

        if self.size_in_MB() > max_size:
            raise Exception(f"File size is larger than maximum ({max_size} MB)")
        else:
            logger.info(f"file size ({self.size_in_MB()}MB) is less than max size ({max_size}MB)")

    ##################
    # status checkers
    ##################

    def server_has_received(self):
        if any(log.get("event") == TRANSCRIPTION_STATUSES[2] for log in self.event_logs): 
            return True
        else:
            return False

    # TODO might do a getter/setter function to extract the db logic out
    def get_event_logs(self): 
        if hasattr(self, "event_logs") == False:
            self.event_logs = []
            ref = self.transcribe_request_ref()
            event_log_ref = ref.collection("event_logs")
            docs = event_log_ref.stream()
            for doc in docs:
                self.event_logs.append(doc.to_dict())


        return self.event_logs

    def last_request_has_stopped(self):
        """
        Checks updated_at and makes sure a reasonable amount of time has passed since the last request
        gets called when the status is not an error, but client suspects that it should be, and was stopped without the error getting handled
        NOTE client should also do something like this and not request a "resume" unless the reasonable amount of time has already passed
        assumes we already refreshed record from firestore, eg in teh resume_request endpoint

        Err on side of waiting. Don't want them hitting this too much and confusing our operation in the middle
        Ideally, this helper is never necessary, since we handle all of the errors and mark the record accordingly, so can be extra cautious to not allow them to retry too quickly
        """
        status = self.status
        elapsed_time = self.elapsed_since_last_event()
        logger.info(f"elapsed time is {elapsed_time}")

        if status == TRANSCRIPTION_STATUSES[0]: # uploading
            # hopefully if they error here, we'll just make them upload again...should never have to ask the server. 
            # but setting reasonable time anyways, since this is just a helper
            # assumes at least 1/5 MB / sec internet connection (except for that 100 = 1 min...)
            return elapsed_time > self.size_in_MB() * 5

        elif status == TRANSCRIPTION_STATUSES[1]: # uploaded
            # we mark as received almost instantaneously, this should be quick
            # but on the other hand, sometimes the server might have been sleeping, et cetera
            return elapsed_time > 200

        elif status == TRANSCRIPTION_STATUSES[2]: # processing-file (aka server has received)
            # takes longer if have to transcode from whatever > flac. Otherwise, only have some quick variable setting (much less than 1 sec), some firestore calls, and a quick roundtrip request to Google's API that confirms they started the transcript, and we should be marking as transcribing
            return elapsed_time > (100 + self.size_in_MB() * 10 if self.file_extension != "flac" else 100)

        elif status == TRANSCRIPTION_STATUSES[3]: # transcribing
            # could take awhile. But a 25 MB sized file should not take 7 min (which would be 100 + size * 25) so doubling that should be plenty
            return elapsed_time > (100 + self.size_in_MB() * 50)

        elif status == TRANSCRIPTION_STATUSES[4]: # "processing-transcription" (means that transcription is complete)
            # should be pretty fast, just iterate over transcript, some var setting, set to firestore a few times, and ret
            return elapsed_time > (100 + self.size_in_MB() * 1)

        elif status == TRANSCRIPTION_STATUSES[5]: # "transcription-processed"
            # stopped because done
            return True

        elif status == TRANSCRIPTION_STATUSES[6]: # server-error
            return True

        elif status == TRANSCRIPTION_STATUSES[7]: # transcribing-error
            return True

    def check_transcription_progress(self):
        """
        https://google-cloud-python.readthedocs.io/en/0.32.0/_modules/google/api_core/operation.html
        https://googleapis.dev/python/google-api-core/latest/operation.html
        """
        operation_dict = get_operation(self.transaction_id)
        metadata = operation_dict["metadata"]
        logger.info("metadata from check progress call: ")
        logger.info(metadata)
        # 100 (int) if done
        self.transcript_metadata = {}
        # it seems that sometimes it doesn't return the progressPercent...maybe when it's still initializing or something? Seems strange, but I've only seen 100% return so far haha
        self.transcript_metadata["progress_percent"] = metadata.get("progressPercent", 0)
        # format: '2020-04-25T21:22:07.436054Z'
        self.transcript_metadata["start_time"] = to_timestamp(metadata["startTime"])
        # format: : '2020-04-25T21:22:14.434078Z'
        self.transcript_metadata["last_updated_at"] = to_timestamp(metadata['lastUpdateTime'])

        if operation_dict.get("error"):
            # TODO have to test, not sure if this is working as I would expect
            # force user to retry
            # not sure what the error value will look like, but whatever
            self.mark_as_transcribing_error(operation_dict.get("error", "UNKNOWN-ERROR"))
            # TODO perhaps try again, perhaps depending on the type of error message
            # unless we just want to let the client just request a retry (which is most of the time true, it is getting more and more rare where the server returns an error, but retrying fixes it)
            return

        # unfortunately, if not done, doesn't set this...so don't access directly
        elif operation_dict.get("done"):
            response = operation_dict["response"]
            print(f"got response: \n{response}\n")
            print(f"what is done? : {operation_dict.get("done")}\n")
            results = response["results"]
            self.mark_as_transcribed()
            self.handle_transcript_results(results)


        # persist progress whether or not we're done
        self.persist()
        self.persist_transcript_data()
        return
        

    ##################################################
    # helpers for interacting with Google Speech API 
    ################################################

    def setup_request(self):
        """
        build a config_dict and audio dict to send to Google
        - does not send anything, just prepares the data to send
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
                logger.info("Sending with multiple channels")
                config_dict["audio_channel_count"] = 2 # might try more later, but I think there's normally just two
                config_dict["enable_separate_recognition_per_channel"] = True
            
            logger.info("sending file: " + self.filename)
            # TODO consider sending their config object...though maybe has same results. But either way, check out the options in beta https://googleapis.dev/python/speech/latest/gapic/v1p1beta1/types.html#google.cloud.speech_v1p1beta1.types.RecognitionConfig
            logger.info("sending with config" + json.dumps(config_dict))
            
            request_params = {
                "audio": audio,
                "config": config_dict,
            }

            self.request_params = request_params

        except Exception as error:
            # mark request status in firestore 
            self.mark_as_server_error(error)
            # bubble up error
            raise error


    # for when status "processing-file" (aka received_by_server)
    # TODO if "server-error", have server check things and make sure it's a kind of error that we want to retry, or if not, make the necessary changes before trying again.
    def request_long_running_recognize(self):
        logger.info("----------------------------------------------------------------")
        try:
            logger.info(f"Attempt # {self.attempt_count()}")

            logger.info("options here is: " +  json.dumps(self.request_options))
            # this is initial response, not complete transcript yet
            # TODO handle if there's no file there, ie it got deleted but they request again or something
            operation_future = speech_client.long_running_recognize(self.request_params['config'], self.request_params['audio'], retry=reset_retry)
            # NOTE for some reason operation_future.metadata returns None
            self.mark_as_transcribing(operation_future)

        except Exception as error:
            logger.error(traceback.format_exc())

            # TODO or maybe try passing in details to the REtry arg?
            logger.error('Error while doing a long-running request:')
            logger.error(error)
            # TODO add back in maybe, but for now keep things simple
            if (self.failed_attempts < 2):
                # need at least two, one for if internal error, and then if another is for channels 
                self.failed_attempts += 1

                # https://cloud.google.com/speech-to-text/docs/error-messages
                if (str(error) in [
                    # got with fileout.wav. code 3 
                    "Must use single channel (mono) audio, but WAV header indicates 2 channels.",  
                    # or is it this one?
                    "400 Must use single channel (mono) audio, but WAV header indicates 2 channels.",
                    # got with fileout.flac 
                    "400 Invalid audio channel count",
                    "400 audio_channel_count `1` in RecognitionConfig must either be unspecified or match the value in the FLAC header `2`.",
                ]):

                    # try again with different channel configuration
                    logger.info("trying again, but with multiple channel configuration.")
                    self.request_options["multiple_channels"] = True
                    # call this again, to update the params to send
                    self.setup_request()
                    self.request_long_running_recognize()

                elif ("Connection reset by peer" in str(error)):
                    # NOTE should not get these anymore due to new retry strategy
                    # NOTE I hate this error... just retry it
                    # I think teh full str is: ('Connection aborted.', ConnectionResetError(104, 'Connection reset by peer'))
                    # at least sometimes
                    self.request_long_running_recognize()

                elif ("13" in str(error)):
                    # this is internal error Error while doing a long-running request: Error: 13 INTERNAL
                    # not tested TODO

                    logger.info("internal Google error, so just trying same thing again")
                    self.request_long_running_recognize()

                elif ("WAV header indicates an unsupported format." == str(error)):
                    # TODO panic
                    # not tested TODO
                    # TODO don't let them retry too many times, it'll hit some quota or something probably
                    # don't bother retrying...
                    self.mark_as_transcribing_error(error)

                elif "400 Invalid recognition 'config': bad sample rate hertz." == str(error):
                    # TODO try again with different hertz? 
                    pass

                else:
                    logger.error("well then what was our error??")
                    logger.error(str(error))
                    self.mark_as_transcribing_error(error)
            else:
                # note that it might be our fault for sending them something, but we are not the ones directly throwing the error, so it is a transcribing error
                self.mark_as_transcribing_error(error)


    # TODO remane "process transcript results"
    def handle_transcript_results(self, results):
        """
        takes completed transcript results and processes it
        maybe in future, store base64. Not necessary for now though, and we're billed by amount of data is stored here, so bet_ter not to. There's cheaper ways if we want to do this


        NOTE this should only have file_path if it was an uploads to storage (ie client didn't send base64)

        prepare to send to firestore
        want sorted by filename so each file is easily grouped, but also timestamped so can support multiple uploads
        also want it to be easily placeable in a url without any difficulty
        TODO put in function that first finds out that Google speech api is finished
        array of objects with single key: "alternatives" which is array as well
        need to convert to objects or arrays only, can't do other custom types like "SpeechRecognitionResult"

        could also grab the name of the request (it's a short-ish unique assigned by Google integer) if ever want to match this to the api call to google
        """

        if type(results) is not list:
            # for when calling operation.result() straight from the operation_future received after the initial request to transcribe
            mapped_results = []
            for result in results:
                result_dict = {
                    "channel_tag": result.get("channel_tag"),
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

            self.utterances = mapped_results
            # Some logger stuff
            logger.info("\n Transcript results: \n")
            for result in results:
                # First alternative is the most probable result
                alt = result.alternatives[0]
                logger.info(u"Transcript for this result: {}".format(alt.transcript))

        else:
            # for when get operation from operation api directly
            self.utterances = results
            logger.info(f"utterances: {utterances}")
            for result in results:
                # TODO remove this when done debugging
                logger.info(f"result: {result}")
                # First alternative is the most probable result
                alt = result["alternatives"][0]
                logger.info(u"Transcript for this result: {}".format(alt["transcript"]))

        logger.info("setting data to transcripts")

        # cleanup storage and db records
        # TODO add error handling if fail to delete, so that it is marked as not deleted. Perhaps a separate try/catch so we know this is what fails, and not something after.
        # Or alternatively, something that tracks each ste_p and marks the last completed ste_p so we know where something stopped and can pick it up later/try again later
        # TODO put in separate method
        for path in [self.file_path, self.original_file_path]:
            if (path):
                # delete file from cloud storage (bucket assigned in the admin initializeApp call)

                try:
                    blob = bucket.blob(path)
                    if reset_retry(blob.exists)():
                        logger.info("deleting file from " + path)
                        reset_retry(blob.delete)()
                        logger.info("deleted file from " + path)

                except Exception as error:
                    # typically something like: "ConnectionResetError: [Errno 104] Connection reset by peer"
                    # tracked here: https://github.com/googleapis/google-cloud-python/issues/5879#issuecomment-535135348
                    # official temp solution is here: https://github.com/googleapis/google-cloud-python/issues/5879#issuecomment-535135348
                    logger.error("error deleting file " + path)
                    logger.error(error)
                    if "Connection reset by peer" in str(error):
                        # if the above decorator doesn't work, retry here
                        pass

        # mark upload as finished transcribing
        self.mark_as_processed()
        return


    ##############################
    # File manipulation methods
    ##########################
    def makeItFlac(self, data, options = {}):
        """
        converts file (eg mp3, wav, mp4) to flac file
        - Use case is that even mp3 files seem to work better when converted to flac first for whatever reason
        - base on https://github.com/firebase/functions-samples/blob/master/ffmpeg-convert-audio/functions/index.js
        - TODO might be better in the future, for more flexibility and ease of use, to just use ffmpeg-static and bash code rather than a wrapper, so can write exactly as it would be in the command line. However, have to figure out how to install a binary in heroku...and note that they cycle machines
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


    def persist(self):
        data = self.__dict__
        cleaned_data = TranscribeRequest.cleanup_dictionary(data)
        transcribe_request_ref = self.transcribe_request_ref()
        transcribe_request_ref.set(cleaned_data, merge=True)


    def persist_transcript_data(self):
        """
        NOTE is persisting the transcript, not the TranscriptRequest. 
        - Basically just called when transcript is complete. Though maybe later will write out the transcript as it's being made, so want a constant ref after all. Though that could be achieved by just persisting the transcript_id on the transcript_request record
        - data is dictionary, based on Transcribe class instance
        - sets data to the transcript ref in firestore
        - only for completed transcripts (incomplete should be at transcribeRequests ref)
        - doc_name is unique identifier for this transcription, different for each version of the transcript even for the same file

        TODO only set attributes needed for the transcript, don't want everything on this thing!
        """
        data = self.__dict__
        cleaned_data = TranscribeRequest.cleanup_dictionary(data)
        doc_ref = self.transcript_document_ref()
        doc_ref.set(cleaned_data)

    #############################
    # status marking methods (for persisting in firestore)
    # TODO DRY this up. Can just persist the whole instance to firestore.
    #############################
    def mark_as_received(self):
        self._update_status(TRANSCRIPTION_STATUSES[2], other={ # processing-file
        }) 

    def mark_as_transcribing(self, operation_future):
        """
        operation_future is an operation_future received from Google in response to hitting their speech to text api
        """

        operation_name = operation_future.operation.name
        logger.info("operation name is: " + operation_name)


        # https://google-cloud-python.readthedocs.io/en/0.32.0/core/operation.html
        self._update_status(TRANSCRIPTION_STATUSES[3], other={ # transcribing
            "transaction_id": operation_name,
        }) 

    def mark_as_transcribed(self):

        self._update_status(TRANSCRIPTION_STATUSES[4]) # processing-transcription

    def mark_as_processed(self):
        # logger.info("deleting record of untranscribed upload: " + f"users/{self.user['uid']}/transcribeRequests/{identifier}")

        self._update_status(TRANSCRIPTION_STATUSES[5]) # processing-transcription


    def mark_as_server_error(self, error):
        logger.error("Marking as Server error")
        logger.error(error)
        self._update_status(TRANSCRIPTION_STATUSES[6], other_in_event={
            "error": str(error),
        }) # server-error 

    # keep separate from server error for now, I think they are different enough that we want to handle differently more and more as this server is built out
    def mark_as_transcribing_error(self, error):
        logger.error("Marking as Transcription error")
        logger.error(error)
        self._update_status(TRANSCRIPTION_STATUSES[7], other_in_event={
            # TODO set something better, this is just doing the error code for now
            "error": str(error),
        }) # transcribing-error 

    
    def _update_status(self, status, **kwargs):
        other = kwargs.get("other", {})
        other_in_event = kwargs.get("other_in_event", {})
        """
        set the status without overwriting anything else
        better to not merge but just update the whole thing to db
        if do so, set properties we don't want to persist as not properties but retrievable by method, like request options
        """

        # update self in the current TranscribeRequest
        event_log = {
            **other_in_event, 
            "event": status,
            "time": timestamp()
        }

        self.status = status
        if other_in_event.get("error"):
            error = other_in_event.get("error")
            # set error on obj for easy access
            self.error = str(error)
        else:
            self.error = ""
        self.event_logs.append(event_log)

        transcribe_request_ref = self.transcribe_request_ref()

        updates = {
            **other,
            "status": status,
            "updated_at": timestamp(),
            "error": self.error, # either sets as error or blank string
        }


        # update status (and whatever is in other) to firestore 
        transcribe_request_ref.set(updates, merge=True)
        logger.info("updated status")
        logger.info(updates)

        # log the new event
        event_log_ref = transcribe_request_ref.collection("eventLogs")
        event_log_ref.add(event_log) 


    ################################    
    # class variables
    ################################
    # encoding: 
    # - Google: "The FLAC and WAV audio file format_s include a header that describes the included audio content. You can request recognition for WAV files that contain either LINEAR16 or MULAW encoded audio. If you send FLAC or WAV audio file format in your request, you do not need to specify an AudioEncoding; the audio encoding format is determined from the file header. If you specify an AudioEncoding when you send send FLAC or WAV audio, the encoding configuration must match the encoding described in the audio header; otherwise the request returns an google.rpc.Code.INVALID_ARGUMENT error code."

    # sample rate hertz:  
    # - None lets google set it themselves. 
    # - For some mp3s, this returns no utterances or worse results though
    # - Regarding MP3s, Google's docs say: "When using this encoding, sampleRateHertz has to match the sample rate of the file being used." TODO need to find a way to dynamically test the file to see its sample rate hertz

    # model:  
    # - Google: "Best for audio that is not one of the specific audio models. For example, long-form audio. Ideally the audio is high-fidelity, recorded at a 16khz or greater sampling rate."

    _base_config = {
        "encoding": enums.RecognitionConfig.AudioEncoding.LINEAR16,
        "language_code": 'km-KH',
        "sample_rate_hertz": None, 
        "enable_automatic_punctuation": True,
        "model": "default", 
        "max_alternatives": 3, # I think it's free, so why not get more ha
        "enable_word_confidence": True,
        "enable_word_time_offsets": True, # returns timestamps
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
