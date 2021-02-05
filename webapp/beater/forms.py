from django import forms
from django.forms import ModelForm
from .models import Playlist, Device 

class PlaylistForm(forms.Form):
    name = forms.CharField(max_length=50)

class DeviceForm(ModelForm):
    class Meta:
        model = Device 
        fields = ['name', 'ip_address', 'agent_base_url', 'is_active']
        
