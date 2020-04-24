
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


