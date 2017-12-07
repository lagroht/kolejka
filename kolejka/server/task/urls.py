# vim:ts=4:sts=4:sw=4:expandtab

from django.conf.urls import url

from . import views

app_name = 'blob'
urlpatterns = [
    url(r'^hash/(?P<hash>[0-9a-f]+)/?$', views.blob),
    url(r'^(?P<key>[0-9a-f]*)/?$', views.reference),
]
