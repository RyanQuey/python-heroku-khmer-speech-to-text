from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
import os
import json
from firebase_admin import firestore
import traceback
from .helpers import TRANSCRIPTION_STATUSES 

# from .transcribe import request_long_running_recognize, setup_request
from .transcribe_class import TranscribeRequest

from copy import deepcopy
import logging
logger = logging.getLogger('testlogger')

####################################
# Helpers
####################################
# use custom response class to override HttpResponse.close()
# NOTE no longer needing to use this though, so transition off of it
class LogSuccessResponse(HttpResponse):
    def close(self):
        super(LogSuccessResponse, self).close()

        # do whatever you want, this is the last codepoint in req handling
        all_of_it = self.getvalue()
        my_json = json.loads(all_of_it)
        data = my_json["data"]
        request = my_json["request"]
        options_dict = my_json["options_dict"]
        # TODO do this in course of normal http transaction, but only request, don't wait for the transcription to finish


        logger.info("all done transcribing and setting and cleaning up")

###################################
# Endpoints
###################################

# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def transcribe(req): 
    """
    Performs asynchronous speech recognition request on an audio file (< 480 minutes)

    fields:
      # TODO update fields
      file_path URI for audio file in Cloud Storage, e.g. gs://[BUCKET]/[FILE]
    """

    transcribe_request = False

    try:
        if req.method == "POST":
            # data = deepcopy(req.POST)
            file_data = json.loads(req.body)
            transcribe_request = TranscribeRequest(file_data)

            # mark request as received in firestore 
            transcribe_request.mark_as_received()

            transcribe_request.setup_request()
             
            transcribe_request.request_long_running_recognize()
            # an async func, should not stop returning the response
            # TODO later, optionally convert file
            # transcribe
            response = HttpResponse(json.dumps({
                "file_data": file_data,
                "request_options": transcribe_request.request_options,
                "request": request,
            }), content_type='application/json')
            
            logger.info(response)

        else:
            logger.info(req.method)
            html = f"<html><body>Needs to be a post....</body></html>"
            response = HttpResponse(html)

        return response
        logger.info("now returning response")

    except Exception as error:
        logger.info("error transcribing file")
        error_response = _log_error(error, transcribe_request)
        return error_response


@csrf_exempt
def resume_request(req): 
    """
    sometimes user will ask to resume a transcription if it got stopped in the middle

    Goals: 
    - avoid unnecessary requests to the Google API, to reduce costs and server strain
    - make everything really seamless and easy for the end-user
    """
    transcribe_request = False

    try:
        file_data = json.loads(req.body)
        transcribe_request = TranscribeRequest(file_data)

        # check to see current status
        transcribe_request.refresh_from_db()
        status = transcribe_request.status()
        logger.info("Status is: " + status)

        # TODO need to import this constant
        if status == TRANSCRIPTION_STATUSES[0]: # uploading
            # whoops...shouldn't be here!
            # check if there is a file and storage, then restart if there is
            # if there isn't, tell client to prompt reupload
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[1]: # uploaded
            # should not allow client to request a resume if only uploaded, unless updated_at was long enough ago. But eventually will check server side as well
            # check updated_at, then restart if too long ago
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[2]: # server-received
            # check updated_at, then restart if too long ago
            # note that this stage often takes a while, since sometimes it means converting large files from one format to flac
            # TODO 
            message = "Not yet handling "


        elif status == TRANSCRIPTION_STATUSES[3]: # transcribing
            # check with google via operation
            # use transaction_id

            # if status says our server is currently processing, then wait a couple seconds, check db again, and if still processing, then assume it errored out somewhere
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[4]: # "transcription-complete"
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[5]: # "transcription-processed"
            # do nothing...tell client it's all done. 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[6]: # server-error
            # go through and make sure to mark as received if not already
            if transcribe_request.server_received_at == None:
                transcribe_request.mark_as_received()

            # check to see if transcribing already by checking if we have a transaction ID. Maybe we errored while processing, and so can try to not have to request from google a second time, and just wait
            if transcribe_request.transaction_id == None: 
                # setup the request again
                transcribe_request.setup_request()
                transcribe_request.request_long_running_recognize()

                message = "Starting to ask Google for transcription again"

            else:
                # check status, if done then can return finished transcription
                # TODO 
                message = "Everything is fine, just waiting for Google to transcribe"


        elif status == TRANSCRIPTION_STATUSES[7]: # transcribing-error
            # try transcribing again, unless error requires changing the file or options first
            # TODO 
            message = "Not yet handling "

        return HttpResponse(json.dumps({
            "message": message
        }), content_type='application/json')

    except Exception as error:
        logger.error("error resuming request")
        error_response = _log_error(error, transcribe_request)
        return error_response


# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def check_status(request): 
    """
    - Client will poll this endpoint periodically to check on how things are
    - Does stuff like resume_request but only checks, doesn't actually transcribe
    - If everything runs smoothly, will keep asking until Google is done transcribing and then will get the transcription
    """
    pass
    # if (status == "ready" or something): (But do in transcriptRequest obj)

            # result = operation_future.result()

            # # Get a Promise re_presentation of the final result of the job
            # # this part is async, will not return the final result, will just write it in the db
            # # Otherwise, will timeout
            # transcription_results = result.results
            # # NOTE this might not be latest metadata, might be data from before it's finished. TODO try calling reload if it's not latest?
            #     
            # self.handle_transcript_results(transcription_results, transaction_name)

def _log_error(error, transcribe_request):
    logger.error(traceback.format_exc())
    # TODO move this error handling to more granular handling so can handle better. Don't do it here.
    if transcribe_request:
        transcribe_request.mark_as_server_error(error)
    else:
        logger.info("no transcribe_request instance instantiated yet; leaving error logging to the client")

    return HttpResponseServerError("Server errored out during transcription")
