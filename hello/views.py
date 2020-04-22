from django.shortcuts import render
from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
import os
import json
from firebase_admin import firestore
import traceback

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

    try:
        if req.method == "POST":
            # data = deepcopy(req.POST)
            file_data = json.loads(req.body)
            transcribeRequest = TranscribeRequest(file_data)

            # mark request as received in firestore 
            transcribeRequest.mark_as_received()

            request = transcribeRequest.setup_request()
             
            transcribeRequest.request_long_running_recognize()
            # an async func, should not stop returning the response
            # TODO later, optionally convert file
            # transcribe
            response = HttpResponse(json.dumps({
                "file_data": file_data,
                "request_options": transcribeRequest.request_options,
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
        logger.error(traceback.format_exc())


        return HttpResponseServerError("Server failed to handle")


# sometimes user will ask to resume a transcription if it got stopped in the middle
@csrf_exempt
def resume_request(req): 
    file_data = json.loads(req.body)
    transcribeRequest = TranscribeRequest(file_data)

    # check to see current status
    transcribeRequest.refresh_from_db()

    # TODO need to import this constant
    if status == TRANSCRIPTION_STATUSES[0]: # uploading
        # whoops...shouldn't be here!
        # check if there is a file and storage, then restart if there is
        # if there isn't, tell client to prompt reupload
        # TODO 
        pass

    elif status == TRANSCRIPTION_STATUSES[1]: # uploaded
        # check updated_at, then restart if too long ago
        # TODO 
        pass

    elif status == TRANSCRIPTION_STATUSES[2]: # server-received
        # check updated_at, then restart if too long ago
        # TODO 
        pass


    elif status == TRANSCRIPTION_STATUSES[3]: # transcribing
        # check with google via operation
        # use transaction_id

        # if status says our server is currently processing, then wait a couple seconds, check db again, and if still processing, then assume it errored out somewhere
        # TODO 
        pass

    elif status == TRANSCRIPTION_STATUSES[4]: # "transcription-complete"
        # TODO 
        pass

    elif status == TRANSCRIPTION_STATUSES[5]: # "transcription-processed"
        # do nothing...tell client it's all done. 
        pass

    elif status == TRANSCRIPTION_STATUSES[6]: # server-error
        # TODO 
        pass


    elif status == TRANSCRIPTION_STATUSES[7]: # transcribing-error
        # TODO 
        pass



# client will poll this endpoint periodically to check on how things are
# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def check_status(request): 
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

