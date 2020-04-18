from django.shortcuts import render
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from .models import Greeting
from .transcribe import download_file

from google.cloud import firestore
from google.cloud import storage
from google.cloud import speech_v1p1beta1
from google.cloud.speech_v1p1beta1 import enums
import logging
logger = logging.getLogger('testlogger')

import os

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
@csrf_exempt
def transcribe(request): 
    """
    Performs asynchronous speech recognition on an audio file

    fields:
      storage_uri URI for audio file in Cloud Storage, e.g. gs://[BUCKET]/[FILE]
    """

    logger.info("env: " + os.environ.get('DJANGO_ENV'))

    if request.method == "POST":
        data = request.POST.copy()
        logger.info(data)

        # extract the form field data
        storage_uri = request.POST.get('storage_uri', '')
         
    	# download file according to url received in post
        download_file(storage_uri)
    	# TODO later, convert file
    	# transcribe
    else:
        logger.info(request.method)


    html = f"<html><body>It is now {storage_uri}.</body></html>"
    return HttpResponse(html)

