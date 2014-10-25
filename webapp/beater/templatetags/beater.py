from django import template

register = template.Library()

@register.filter(name='has_status')
def has_status(album, status):	
	return album.has_status(status)
