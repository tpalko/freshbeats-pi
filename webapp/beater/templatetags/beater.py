from django import template

register = template.Library()

@register.filter(name='has_status')
def has_status(album, status):	
	return album.has_status(status)

@register.filter(name='getattribute')
def getattribute(obj, property_name):
	if property_name in obj:
		return obj[property_name]
	return None