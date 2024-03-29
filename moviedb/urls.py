"""moviedb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from movie.authentication import NopassLoginView


urlpatterns = [
    # urls admin for django-admin-honeypot
    path("admin/", include("admin_honeypot.urls", namespace="admin_honeypot")),
    path("secretadmin/", admin.site.urls),
    # include urls app movie
    path("", include("movie.urls")),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if settings.USE_NO_USER_PASSWORD:
    urlpatterns += [path("accounts/login/", NopassLoginView.as_view())]
else:
    urlpatterns += [path("accounts/login/", auth_views.LoginView.as_view())]
