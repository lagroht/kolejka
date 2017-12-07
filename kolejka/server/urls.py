# vim:ts=4:sts=4:sw=4:expandtab

from django.conf.urls import include, url
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth import urls as auth_urls

from kolejka.server.main import urls as main_urls
from kolejka.server.blob import urls as blob_urls
from kolejka.server.task import urls as task_urls

urlpatterns = [
#    url(r'^accounts/login/', auth_views.LoginView.as_view(template_name='admin/login.html')),
    url(r'^accounts/login/?', auth_views.login),
    url(r'^accounts/', include(auth_urls)),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^blob/', include(blob_urls)),
    url(r'^task/', include(task_urls)),
    url(r'', include(main_urls)),
]