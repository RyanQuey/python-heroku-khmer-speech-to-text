# NOTE/TODO if ever import into more than one file, will need to conditionally initialize some of these services to make sure they only run once
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
from googleapiclient import discovery
from google.api_core import operations_v1
from oauth2client.client import GoogleCredentials
from pprint import pprint

# experiment with logging
import traceback
import logging
import json
from copy import deepcopy
##########################
# constants
#########################

# TODO get all these constants to somewhere else and import them
# probably grab some of the class vars too eg _base_config
APP_NAME = "khmer-speech-to-text"
BUCKET_NAME = "khmer-speech-to-text.appspot.com"
logger = logging.getLogger('testlogger')
# provide alternate path in case we don't want to set the GOOGLE_APPLICATION_CREDENTIALS, though this matters less with honcho
admin_key_location = os.environ.get('ADMIN_KEY_LOCATION')
from pprint import pprint
default_key_location = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')

# path to service account json file
# don't need to set the credentials, everything is automatically derived from system GOOGLE_APPLICATION_CREDENTIALS env var. But if need a different credential, can set it 
service_account = admin_key_location or default_key_location

cred = credentials.Certificate(service_account)
firebase_admin.initialize_app(cred, {
    'storageBucket': BUCKET_NAME,
    'projectId': APP_NAME,
    'databaseURL': f"https://{APP_NAME}.firebaseio.com/",
})

# for getting operation_futures
# don't know if this will work, officially they have sample like so: 
# if don't want to set, GOOGLE_APPLICATION_CREDENTIALS can try this
# https://github.com/googleapis/google-cloud-python/issues/1883#issuecomment-279214250
# TODO remove; I think not using this, need to call the operations.get from the speech client, or it doesn't find the operation
# credentials = GoogleCredentials.get_application_default()
# but trying to use the firebase admin creds for now
# google_api_service = discovery.build('cloudresourcemanager', 'v1', credentials=credentials)

# not sure why, but doing admin.firestore.Client() doesn't work on its own
# NOTE should now, we're setting the GOOGLE_APPLICATION_CREDENTIALS now
db = firestore.Client.from_service_account_json(service_account)

# alias so don't have to write out the beta part
# for now only using the beta

speech = speech_v1p1beta1
speech_client = speech.SpeechClient.from_service_account_json(service_account)

operations_api = operations_v1.OperationsClient(speech_client.transport.channel)
def get_operation_old(operation_name):
    """
    - I'm currently not using this, but reserving this code for future use especially since it is difficult to locate within the documentation
    - Borrowing code from https://github.com/googleapis/python-speech/issues/8
    - To get metadata: get_operation(name).metadata
    """
    op = operations_api.get_operation(operation_name)
    return op

def get_operation(operation_name):
    """
    - Borrowing code from https://github.com/googleapis/python-speech/issues/8
    - operation returned is similar to what is returned by the original long-running request, but is a dict
    """
    speech_service = discovery.build('speech', 'v1p1beta1')
    request = speech_service.operations().get(name=operation_name)
    operation_dict = request.execute()
    return operation_dict

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

# not using right now
# isDev = settings.ENV == "DEVELOPMENT"

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
    # includes converting to different encoding (eg mp4 > flac)
    # server sets
    "processing-file", 

    # 3
    # when Google has started the operation to transcribe the file, and is currently transcribing.   
    # server sets
    "transcribing", 

    # 4
    # Google finished transcribing, but we haven't yet processed their transcription for whatever reason
    "processing-transcription",

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





#########################################
# Helpers
################################

def timestamp():
    # format like this: "20200419T016208Z"
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ") 


# TODO maybe we want the equivalent for python
# Express middleware that validates Firebase ID Tokens passed in the Authorization Ht_tP header.
# The Firebase ID token needs to be passed as a Bearer token in the Authorization Ht_tP header like this:
# "Authorization: Bearer <Firebase ID Token>".
# when decoded successfully, the ID Token content will be added as "req["user"]".
#  validate_firebaseIdToken(req, res, next) =>:
#
#    if ((!req["headers"]["authorization"] || !req["headers"]["authorization"].start_sWith('Bearer ')) &&
#        !(req["cookies"] && req["cookies"].__session)):
#      print('No Firebase ID token was passed as a Bearer token in the Authorization header.',
#          'Make sure you authorize your request by providing the following Ht_tP header:',
#          'Authorization: Bearer <Firebase ID Token>',
#          'or by passing a "__session" cookie.')
#      res.status(403).send('Unauthorized')
#      return
#    }
#
#    let idToken
#    if (req["headers"]["authorization"] && req["headers"]["authorization"].start_sWith('Bearer ')):
#      # Read the ID Token from the Authorization header.
#      idToken = req["headers"]["authorization"].split('Bearer ')[1]
#    } else if(req["cookies"]):
#      # Read the ID Token from cookie.
#      idToken = req["cookies"].__session
#    else:
#      # No cookie
#      res.status(403).send('Unauthorized')
#      return
#    }
#
#    try:
#      decodedIdToken = admin.auth().verifyIdToken(idToken)
#      req["user"] = decodedIdToken
#
#      # NOTE right now don't care if email is verified
#      # if (!req["user"]["email_verified"]):
#      #   # make them verify it first
#      #   print('Email not verified')
#      #   res.status(403).send('Unauthorized')
#      #   return
#      # }
#      # currently only allowing whitelisted users to use
#      if (!WHITE_LISTED_USERS.includes(req.user.email) && !req["user"]["email"].match(/rlquey2\+.*@gmail.com/)):
#        res.status(403).send("Your email isn't allowed to use our service yet; please contact us to get your account setup")
#        return
#      }
#
#      next()
#      return
#    } catch (error):
#      print('Error while verifying Firebase ID token:', error)
#      res.status(403).send('Unauthorized')
#      return
#    }
#  },

