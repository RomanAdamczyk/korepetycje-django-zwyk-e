from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm


class LoginForm(forms.Form):
    username = forms.CharField(max_length=65)
    password = forms.CharField(max_length=65, widget=forms.PasswordInput)

class RegisterForm(UserCreationForm):
    usable_password = None
    code = forms.CharField(label='Kod zaproszeniowy', required=True, widget=forms.PasswordInput)
    
    class Meta:
        model=User
        fields = ['username','email','password1','password2','code'] 

