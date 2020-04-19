from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Greeting
from .transcribe import request_long_running_recognize, setup_request

from copy import deepcopy
import logging
logger = logging.getLogger('testlogger')

import os
import json
from django.http import HttpResponse


APIS = ["v1", "v1p1beta"]
BASE_REQUEST_OPTIONS = {
  # maybe better to ask users to stop doing multiple channels, unless it actually helps
  "multiple_channels": False, 
  "api": APIS[1],
  "failed_attempts": 0, # TODO move to diff dict, since it's not an option
}

####################################
# Helpers
####################################
# use custom response class to override HttpResponse.close()
class LogSuccessResponse(HttpResponse):
    def close(self):
        super(LogSuccessResponse, self).close()

        # do whatever you want, this is the last codepoint in request handling
        all_of_it = self.getvalue()
        my_json = json.loads(all_of_it)
        data = my_json["data"]
        request = my_json["request"]
        options_dict = my_json["options_dict"]
        request_long_running_recognize(request, data, options_dict)

        logger.info("all done transcribing and setting and cleaning up")

# Create your views here.
def index(request):
    # return HttpResponse('Hello from Python!')
    return render(request, "index.html")


# TODO remove
def db(request):

    greeting = Greeting()
    greeting.save()

    greetings = Greeting.objects.all()

    return render(request, "db.html", {"greetings": greetings})

# not receiving these requests from the browser, so skipping. TODO or am I?
# TODO might not need this since doing the csrf host whitelisting
@csrf_exempt
def transcribe(request): 
    """
    Performs asynchronous speech recognition on an audio file

    fields:
      url URI for audio file in Cloud Storage, e.g. gs://[BUCKET]/[FILE]
    """

    if request.method == "POST":
        # data = deepcopy(request.POST)
        data = json.loads(request.body)
        # starts with base options and gets mutated over time
        options_dict = deepcopy(BASE_REQUEST_OPTIONS)
        request = setup_request(data, options_dict)
         
    	# download file according to url received in post

        # an async func, should not stop returning the response
        # want to keep going after we finish this task
        
    	# TODO later, optionally convert file
    	# transcribe
        logger.info("now returning response")
        response = LogSuccessResponse(json.dumps({
            "data": data,
            "options_dict": options_dict,
            "request": request,
            }), content_type='application/json')
        logger.info(response)

        return response
    else:
        logger.info(request.method)
        html = f"<html><body>Wasn't a post....</body></html>"
        return HttpResponse(html)
