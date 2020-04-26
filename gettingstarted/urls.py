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
    path("admin/", admin.site.urls),
]
