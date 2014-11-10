from django import template
from django.utils.safestring import mark_safe
from urllib.parse import urlencode, parse_qs

register = template.Library()
def albug(value):
	if (value == 0):
		return "None"
	return mark_safe("<a href='https://bugs.archlinux.org/task/"+str(value)+"'>"+str(value)+"</a>")
register.filter('link_bug', albug)

def JenkinsURL(value):
	return "http://jenkins.arch-ci.org/job/package/%d" % int(value);
register.filter('jenkins_url', JenkinsURL)


def Status(value):
	if value == 0:
		return "Success"
	elif value == 1:
		return "Failure"
	elif value == 2:
		return "In progress"
	elif value == 3:
		return "Removed"
	elif value == -1:
		return "Unbuilt"
	return value
register.filter('status', Status)

def Reason(value):
	if value == 1:
		return "General"
	elif value == 2:
		return "Check"
	elif value == 3:
		return "Source"
	elif value == 4:
		return "Depends"
	elif value == 6:
		return "Hash"
	return value


#these next two functions were taken directly from archweb
class BuildQueryStringNode(template.Node):
	def __init__(self, sortfield):
		self.sortfield = sortfield
		super(BuildQueryStringNode, self).__init__()

	def render(self, context):
		qs = parse_qs(context['current_query'])
		if 'sort' in qs and self.sortfield in qs['sort']:
			if self.sortfield.startswith('-'):
				qs['sort'] = [self.sortfield[1:]]
			else:
				qs['sort'] = ['-' + self.sortfield]
		else:
			qs['sort'] = [self.sortfield]
		return urlencode(qs, True).replace('&', '&amp;')

@register.tag(name='buildsortqs')
def do_buildsortqs(parser, token):
	try:
		tagname, sortfield = token.split_contents()
	except ValueError:
		raise template.TemplateSyntaxError(
				"%r tag requires a single argument" % token)
	if not (sortfield[0] == sortfield[-1] and sortfield[0] in ('"', "'")):
		raise template.TemplateSyntaxError(
				"%r tag's argument should be in quotes" % token)
	return BuildQueryStringNode(sortfield[1:-1])

