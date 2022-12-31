# Python Khmer Speech to Text API

A Django app (deployed on Heroku) for creating and handling long running asynchronous requests to Google Speech API. For instructions and more information, see the [firebase frontend repo](https://github.com/RyanQuey/khmer_speech_to_text).

## Project Architecture
Lifecycle of a healthy, successful upload/transcription request

We track and display progress as the file uploads to Google Storage, as it is transcribed to Google Speech API, and as it is returned and stored by Firebase.

![Uploading audio](https://github.com/RyanQuey/python-heroku-khmer-speech-to-text/raw/master/screenshots/khmer-speech-app.architecture.png)

## Transcript Results
Transcript includes highlights based on accuracy percentage, and lists possible alternatives on hover. Metadata about the file and the transcription is persisted for future reference.

![Transcript Result](https://github.com/RyanQuey/python-heroku-khmer-speech-to-text/raw/master/screenshots/transcript-result.png)

## Running Locally

Make sure you have Python 3 [installed locally](http://install.python-guide.org). 
- Tested on Python 3.6 and 3.7

```sh
# clone the repository
git clone https://github.com/RyanQuey/python-heroku-khmer-speech-to-text.git
cd python-heroku-khmer-speech-to-text

# install venv if don't have it already
sudo apt-get -y install python3-venv

# open the virtual env in current project
python3 -m venv ./venv
source ./venv/bin/activate

# If need to get pip (which, there's a decent chance you won't), can run: 
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# make sure to do this before installing python requirements
# If got following error, will need to install some stuff:
# `You need to install postgresql-server-dev-X.Y for building a server-side extension or libpq-dev for building a client-side application`
# See here: https://stackoverflow.com/a/28938258/6952495
# If you did, will need the following dependencies in order to install django. If so run the following:
sudo apt-get install python-psycopg2 libpq-dev

# if don't have wheel yet
pip3 install wheel

# install project dependencies
python3 -m pip install -r requirements.txt
```


### Now need to set some env vars
```
cp ./.env.sample ./.env
```
You're going to want to go in there and change those env vars to fit your setup. What you need to set:
 - especially one of either ADMIN_KEY_LOCATION or GOOGLE_APPLICATION_CREDENTIALS (don't need both). Get it from google admin console
    * note that you only need one or the other. GOOGLE_APPLICATION_CREDENTIALS is what google libs look for by default, but if you don't want to set that as an environment variable for whatever reason (ie because it is where google libs look by default), can use ADMIN_KEY_LOCATION instead
    * for my account that is live or prod, upload a key to service acct named firebase-adminsdk). Just click "Add Key" and "create new Key" and create a json key. Requires access to firebase sdk, App Engine default service account, Google APIs Service Agent, maybe some others
    * is used for firebase admin, google storage, and google speech to text apis
    * If this isn't setup correctly, after Browser finishes uploading user audio file to Google storage, it will set status of request to "server-error", in browser console, you should see "Internal Server Error", and django logs, `google.api_core.exceptions.PermissionDenied: 403 Missing or insufficient permissions`

![image](https://user-images.githubusercontent.com/22231483/122151793-034dd680-ce15-11eb-8d12-8307a80c1283.png)




### start local server
```
heroku local
```
OR alternatively, can use Honcho for some extra features. My preferred way:
```
python3 -m pip install honcho
honcho start -f Procfile.dev
```

Your app should now be running on [localhost:5000](http://localhost:5000/).

We don't have any actual views, but you can still go there to see if the app is running. 

Now your frontend can hit this python api server.

## Opening a Console
### If using honcho, can open a console

```sh
python3 -m pip install honcho
honcho run python
```

## Deploying to Heroku
To push to Heroku, you'll need to install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli).

Set remote if not already:
```
heroku git:remote -a khmer-speech-to-text-api
```

```sh
# OR if in my current app, which deploys with hook to master branch in github: 
git push

heroku open
```

### Set Env vars
Open the Heroku settings and set the config vars. 
```
TIMES=2
SECRET_KEY='Secret code!!!!'
DJANGO_ENV='PRODUCTION'
GUNICORN_CMD_ARGS="--timeout 300"
ADMIN_KEY_LOCATION='/app/khmer-speech-to-text-a95a2e910a83.json'
GOOGLE_APPLICATION_CREDENTIALS='/app/khmer-speech-to-text-a95a2e910a83.json'
SERVICE_ACCOUNT_JSON='copy in the json from the file' 
```
Just set `SERVICE_ACCOUNT_JSON` using the `google-admin-service-account.json` file (e.g., `khmer-speech-to-text-a95a2e910a83.json`). Just output it as a single line using this: 

```
cat khmer-speech-to-text-a95a2e910a83.json | jq -c
```

You also need to set `ADMIN_KEY_LOCATION` to something, it doesn't matter what really as long as it's pointing at an existing folder, so that the Heroku startup script and take that json and make a file there, and then refer to that file (both the copying and the usage uses the `ADMIN_KEY_LOCATION` var).
UPDATE: CORRECTION It seems like you DO need `GOOGLE_APPLICATION_CREDENTIALS` set, set that to same path as `ADMIN_KEY_LOCATION`. I think `ADMIN_KEY_LOCATION` is used to create the file from the json config var, `GOOGLE_APPLICATION_CREDENTIALS` is used to communicate with GCP API. 

You can take that output and put it directly into the Heroku Config Var.



# Released under MIT License

Copyright (c) 2022 Ryan Quey.

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
