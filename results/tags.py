from django import template
from django.utils.safestring import mark_safe

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
