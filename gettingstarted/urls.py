from django.http import HttpResponse
from django.http import HttpResponseServerError
from django.views.decorators.csrf import csrf_exempt
from django.urls import path, include

from django.contrib import admin

admin.autodiscover()

import hello.views

# To add a new path, first import the app:
# import blog
#
# Then add the new path:
# path('blog/', blog.urls, name="blog")
#
# Learn more here: https://docs.djangoproject.com/en/2.1/topics/http/urls/

urlpatterns = [
    path("request-transcribe/", hello.views.transcribe, name="transcribe"),
    path("resume-request/", hello.views.resume_request, name="resume-request"),
    path("check-status/", hello.views.check_status, name="check-status"),
    # something to add for when using heroku hobby dynos
    path("wake-up/", csrf_exempt(lambda request: HttpResponse('Hello World! Waking up')), name="wake-up"),
    path("admin/", admin.site.urls),
]
