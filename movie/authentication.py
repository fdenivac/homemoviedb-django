# pylint: disable=imported-auth-user

"""
    Login / Logout

    Implements Authentication Backend,  AuthenticationForm, LoginView
        for autehtiication without password for normal user (no admin;staff)

    User without password could be created via :
        from django.contrib.auth.models import User
        User.objects.create(username='guest')
"""

from django import forms
from django.utils.translation import gettext_lazy as _
from django.contrib.auth.views import LoginView
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.forms import AuthenticationForm, UsernameField
from django.contrib.auth.backends import BaseBackend
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import render
from django.core.exceptions import ValidationError, ObjectDoesNotExist


class NopassAuthBackend(BaseBackend):
    ''' Authentification Backend : no password requiried for some user '''
    def authenticate(self, request, username, password):
        try:
            user = User.objects.get(username=username)
            # possible login without password for user not superuser or in staff
            if not (user.is_superuser or user.is_staff) and not user.password and not password:
                success = True
            else:
                success = user.check_password(password)
            if success:
                return user
        except User.DoesNotExist:
            pass
        return None

    def get_user(self, uid):
        try:
            return User.objects.get(pk=uid)
        except ObjectDoesNotExist:
            return None


class NopassLoginForm(AuthenticationForm):
    ''' Authentification form : allow empty password (no required) '''
    username = UsernameField(widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(
        required=False,
        label=_("Password"),
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password'}),
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        user = authenticate(username=username, password=password)
        if not user:
            raise ValidationError(_('Invalid username or password'))
        return self.cleaned_data



class NopassLoginView(LoginView):
    ''' login view (form.get_user() replaced by  authenticate(...) '''
    authentication_form = NopassLoginForm
    template_name = 'registration/login.html'

    def form_valid(self, form):
        username = form.cleaned_data.get('username')
        raw_password = form.cleaned_data.get('password')
        account = authenticate(username=username, password=raw_password)
        auth_login(self.request, account)
        return HttpResponseRedirect(self.get_success_url())



def confirm_logout(request):
    ''' confirm logout dialog '''
    return render(request, 'registration/logout.html', {})

def logout(request):
    ''' logout from site '''
    try:
        session = Session.objects.get(session_key=request.session.session_key)
        session.delete()
    except Session.DoesNotExist:
        pass

    return HttpResponse("You are logged out")
