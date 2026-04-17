from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import Dataset


class DatasetUploadForm(forms.ModelForm):
    """Form for uploading a CSV dataset for bias analysis."""
    class Meta:
        model = Dataset
        fields = ['name', 'file']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'e.g., Loan Approval Dataset 2024',
                'id': 'dataset-name',
            }),
            'file': forms.FileInput(attrs={
                'class': 'file-input',
                'accept': '.csv',
                'id': 'dataset-file',
            }),
        }
        labels = {
            'name': 'Dataset Name',
            'file': 'CSV File',
        }

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.endswith('.csv'):
                raise forms.ValidationError('Only CSV files are supported.')
            if file.size > 52428800:  # 50MB
                raise forms.ValidationError('File size must be under 50MB.')
        return file


class SignUpForm(UserCreationForm):
    """User registration form with email."""
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-input',
            'placeholder': 'your@email.com',
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'form-input',
                'placeholder': 'Choose a username',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Create a password',
        })
        self.fields['password2'].widget.attrs.update({
            'class': 'form-input',
            'placeholder': 'Confirm your password',
        })

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
        return user
