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

###################################
# Controllers 
###################################

# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def transcribe(req): 
    """
    Performs asynchronous speech recognition request on an audio file (< 480 minutes)
    - goes through the entire request process, and if anything fails along the way logs the error, updates status to failed, and sets a message so that user can tell what failed from the react UI

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

            # check the request using our internal criteria before even sending to Google
            transcribe_request.validate_request()
            logger.debug("transcribe request validated!")

            logger.debug("== setting up request payload to send to Google")
            transcribe_request.setup_request()
             
            logger.debug("== sending request payload to Google")
            transcribe_request.request_long_running_recognize()
            # an async func, should not stop returning the response

            # TODO later, optionally convert file
            # transcribe

            # if get here, either it is now transcribing or we handled the error (though that doesn't mean that we continued to retry)
            response = HttpResponse(json.dumps({
                "current_request_data": transcribe_request.__dict__
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
        status = transcribe_request.status
        logger.info(f"Status is now {status}")

        # check the request using our internal criteria before even sending to Google
        transcribe_request.validate_request()
        logger.debug("transcribe request validated!")

        if transcribe_request.last_request_has_stopped() == False:
            logger.info("making them wait a little bit longer")
            message = "Please wait a little longer before requesting, it's only been {} so far".format(transcribe_request.elapsed_since_last_event())

        elif status == TRANSCRIPTION_STATUSES[0]: # uploading
            # whoops...shouldn't be here!
            # check if there is a file and storage, then restart if there is
            # if there isn't, tell client to prompt reupload
            # TODO use better python exception
            transcribe_request.mark_as_server_error(Exception("404 No such object"))
            
            message = "they should try uploading again"

        elif status == TRANSCRIPTION_STATUSES[1]: # uploaded
            # should not allow client to request a resume if only uploaded, unless updated_at was long enough ago. But eventually will check server side as well
            # check updated_at, then restart if too long ago
            # TODO 

            message = _resume_transcribing_or_processing(transcribe_request)

        elif status == TRANSCRIPTION_STATUSES[2]: # processing-file (aka server has received)
            # check updated_at, then restart if too long ago
            # note that this stage often takes a while, since sometimes it means converting large files from one format to flac
            # TODO 

            message = _resume_transcribing_or_processing(transcribe_request)


        elif status == TRANSCRIPTION_STATUSES[3]: # transcribing
            # check with google via operation
            # use transaction_id

            # if status says our server is currently processing, then wait a couple seconds, check db again, and if still processing, then assume it errored out somewhere
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[4]: # "processing-transcription" (means that transcription is complete)
            # TODO 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[5]: # "transcription-processed"
            # do nothing...tell client it's all done. 
            message = "Not yet handling "

        elif status == TRANSCRIPTION_STATUSES[6]: # server-error
            message = _resume_transcribing_or_processing(transcribe_request)

        elif status == TRANSCRIPTION_STATUSES[7]: # transcribing-error
            # try transcribing again, unless error requires changing the file or options first
            # TODO setup to handle different errors from Google. For now, just handling as any other error
            message = _resume_transcribing_or_processing(transcribe_request)

        return HttpResponse(json.dumps({
            "message": message
        }), content_type='application/json')

    except Exception as error:
        logger.error("error resuming request")
        error_response = _log_error(error, transcribe_request)
        return error_response


# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def check_status(req): 
    """
    - Client will poll this endpoint periodically to check on how things are
    - Does stuff like resume_request but only checks, doesn't actually transcribe
    - If everything runs smoothly, will keep asking until Google is done transcribing and then will get the transcription

    TODO 
    - Maybe move to background worker, and just poll whether or not client asks
    """
    # get operation from Google
    # https://cloud.google.com/resource-manager/reference/rest/v1/operations/get

    transcribe_request = False

    try:
        file_data = json.loads(req.body)
        transcribe_request = TranscribeRequest(file_data)

        # check to see current status
        # TODO maybe only check Google depending on current status?
        transcribe_request.refresh_from_db()
        transcribe_request.check_transcription_progress() 

        return HttpResponse(json.dumps({
            "message": "finished checking status",
            "progress_percent": transcribe_request.transcript_metadata["progress_percent"],
            "current_request_data": transcribe_request.__dict__

        }), content_type='application/json')


    except Exception as error:
        logger.error("error resuming request")
        error_response = _log_error(error, transcribe_request)
        return error_response

##########################################
# Controller Helpers
#######################
def _log_error(error, transcribe_request):
    logger.error(traceback.format_exc())
    # TODO move this error handling to more granular handling so can handle better. Don't do it here.
    if transcribe_request:
        if "error" not in transcribe_request.status:
            transcribe_request.mark_as_server_error(error)
        else:
            # assuming already handled...TODO find better way to check if already handled, since it's possible that this error is from last time
            pass
    else:
        logger.info("no transcribe_request instance instantiated yet; leaving error logging to the client")

    return HttpResponseServerError("Server errored out during transcription request")

def _resume_transcribing_or_processing(transcribe_request):
    # go through and make sure to mark as received if not already
    if transcribe_request.server_has_received() == False:
        transcribe_request.mark_as_received()

    # check to see if transcribing already by checking if we have a transaction ID. Maybe we errored while processing, and so can try to not have to request from google a second time, and just wait
    logger.info("checking transaction id")
    if transcribe_request.transaction_id == None: 
        # setup the request again
        logger.info("now setting up ")
        transcribe_request.setup_request()
        transcribe_request.request_long_running_recognize()

        message = "Starting to ask Google for transcription again"

    elif transcribe_request.transaction_complete():
        message = "seems like it's on the way to being returned, so just hold tight"

    else:
        transcribe_request.check_transcription_progress() 
        message = "checked status of already ongoing transcription operation"
        # check status, if done then can return finished transcription
        # TODO 
        # also, need different handling if this was called from a transcribing-error, since presumably this means that it's Google's fault and we probably need do do something beyond just checking the status

    return message


class LogSuccessResponse(HttpResponse):
    """
    use custom response class to override HttpResponse.close()
    NOTE no longer needing to use this though, so transition off of it
    """
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

