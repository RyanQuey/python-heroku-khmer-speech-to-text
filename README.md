# Python Khmer Speech to Text API

A barebones Django app, which can easily be deployed to Heroku.

This application supports the [Getting Started with Python on Heroku](https://devcenter.heroku.com/articles/getting-started-with-python) article - check it out.

## Running Locally

Make sure you have Python 3.7 [installed locally](http://install.python-guide.org). To push to Heroku, you'll need to install the [Heroku CLI](https://devcenter.heroku.com/articles/heroku-cli), as well as [Postgres](https://devcenter.heroku.com/articles/heroku-postgresql#local-setup).

```sh
# clone the repository
git clone https://github.com/RyanQuey/python-heroku-khmer-speech-to-text.git
cd python-heroku-khmer-speech-to-text

# install venv if don't have it already
sudo apt-get -y install python3-venv

# open the virtual env in current project
python3 -m venv venv

# If need to get pip (which, there's a decent chance you won't), can run: 
curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py
python3 get-pip.py

# install project dependencies
python3 -m pip install -r requirements.txt

# If got following error, will need to install some stuff:
# `You need to install postgresql-server-dev-X.Y for building a server-side extension or libpq-dev for building a client-side application`
# See here: https://stackoverflow.com/a/28938258/6952495
# If you did, will need the following dependencies in order to install django. If so run the following:
sudo apt-get install python-psycopg2
sudo apt-get install libpq-dev


# If we were using a db would run this:
# createdb khmer_speech_to_text
# python manage.py migrate
# python manage.py collectstatic

# Now need to set some env vars
cp ./.env.sample ./.env

# You're going to want to go in there and change those env vars to fit your setup

# start local server
heroku local

# OR alternatively, can use Honcho for some extra features
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

```sh
heroku create
git push heroku master

# If had a db:
# heroku run python manage.py migrate

heroku open
```
