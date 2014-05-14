from django import template
from django.utils.safestring import mark_safe

register = template.Library()
def albug(value):
	if (value == 0):
		return "0"
	return mark_safe("<a href='https://bugs.archlinux.org/task/"+str(value)+"'>"+str(value)+"</a>")
register.filter('link_bug', albug)

def JenkinsURL(value):
	return "http://jenkins.arch-ci.org/job/package/%d" % int(value);
register.filter('jenkins_url', JenkinsURL)

