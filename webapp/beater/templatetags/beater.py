from django import template

register = template.Library()

@register.filter(name='has_status')
def has_status(album, status):	
	statuses = map(lambda s: s.status, album.albumstatus_set.all())
	return status in statuses
