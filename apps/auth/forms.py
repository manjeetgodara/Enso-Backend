from django import forms
import requests
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import password_validation
from django.contrib.auth.forms import ReadOnlyPasswordHashField, UserChangeForm as DjangoUserChangeForm
from .models import Users
import json
from environs import Env
env = Env()
env.read_env()
from django.contrib.auth import (
    authenticate, get_user_model, password_validation,
)
class UserCreationForm(forms.ModelForm):
    """A form for creating new users. Includes all the required
    fields, plus a repeated password."""
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput, help_text=password_validation.password_validators_help_text_html())
    password2 = forms.CharField(label='Password confirmation', widget=forms.PasswordInput,help_text=_("Enter the same password as before, for verification."),)



    class Meta:
        model = Users
        exclude = ('password',)

    def clean_password2(self):
        # Check that the two password entries match
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise forms.ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        # Save the provided password in hashed format
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        print(f'Api flow has been in created!')
        env_data = env("ENVIRONMENT")

        if env_data == "PROD":
            api_url = "http://3.111.78.151/chatapp/api/user/create-user/"
            headers = {'Content-Type': 'application/json'}
            data = {
                "name":self.cleaned_data["name"],
                "mobile":self.cleaned_data["mobile"],
                "email":self.cleaned_data["email"],
                "password":self.cleaned_data["password1"],
                "gender":self.cleaned_data["gender"],
                "role":self.cleaned_data["role"],
                "is_active":self.cleaned_data["is_active"],
                "is_staff":self.cleaned_data["is_staff"],
                "is_superuser":self.cleaned_data["is_superuser"],
            }
            print("data: ",data)
            json_data = json.dumps(data)
            print("json_data: ",json_data)
            response = requests.post(api_url, data=json_data, headers=headers)
            print(f'Api flow response: ',response)
            if response.status_code == 200:
                print("API call successful")
            else:
                print("API call failed:", response.status_code, response.text) 
        if commit:
            user.save()
        return user


# class UserChangeForm(forms.ModelForm):
#     class Meta:
#         model = Users
#         fields = ('email', 'name', 'mobile', 'gender', 'role', 'is_active', 'is_staff', 'is_superuser', 'profile_pic', 'organization')

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.fields['password'] = forms.CharField(label="New Password", widget=forms.PasswordInput, required=False)

#     def save(self, commit=True):
#         user = super().save(commit=False)

#         if self.cleaned_data.get('password'):
#             user.set_password(self.cleaned_data['password'])

#         if commit:
#             user.save()

#         return user

class UserChangeForm(DjangoUserChangeForm):
    password = ReadOnlyPasswordHashField(label=_("Password"),
    help_text=_("Raw passwords are not stored, so there is no way to see "
                    "this user's password, but you can change the password "
                    "using <a href=\"../password/\">this form</a>."))

    class Meta:
        model = Users
        fields = ('email', 'name', 'mobile', 'gender', 'role', 'is_active', 'is_staff', 'is_superuser', 'profile_pic', 'organization')

    def clean_password(self):
        return self.initial["password"]
