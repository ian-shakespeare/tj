from django import forms


class UploadForm(forms.Form):
    name = forms.CharField(max_length=64)
    document = forms.FileField()
