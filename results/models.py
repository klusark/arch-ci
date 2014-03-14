from django.db import models

class Result(models.Model):
	package = models.CharField(max_length=200)
	repo = models.CharField(max_length=200)
	jenkins_id = models.IntegerField(default=0)
	status = models.IntegerField(default=0)
	last_built = models.DateTimeField(auto_now = True)
	bug_id = models.IntegerField(default=0)
	flagged = models.BooleanField()
	arch = models.CharField(max_length=200)

