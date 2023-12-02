from django import forms
from django.forms import ModelForm
from .models import Playlist, Device, Mobile

class PlaylistForm(forms.Form):
    name = forms.CharField(max_length=50)

class DeviceForm(ModelForm):
    class Meta:
        model = Device 
        fields = ['name', 'ip_address', 'agent_base_url', 'is_active']
        
class MobileForm(ModelForm):
    class Meta:
        model = Mobile 
        fields = ['name', 'ip_address', 'ssh_username', 'ssh_private_key_path', 'target_path']
