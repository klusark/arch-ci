from django.db import models

class Result(models.Model):
	package = models.CharField(max_length=200)
	repo = models.ForeignKey('Repo')
	jenkins_id = models.IntegerField(default=0)
	status = models.IntegerField(default=0)
	last_built = models.DateTimeField(auto_now_add = True)
	bug_id = models.IntegerField(default=0)
	flagged = models.BooleanField(default=False)
	arch = models.CharField(max_length=200)
	check = models.BooleanField(default=False)
	source = models.BooleanField(default=False)
	def __str__(self):
		return self.package

class Build(models.Model):
	package = models.ForeignKey('Result')
	length = models.IntegerField(default=0)
	time = models.DateTimeField(auto_now = True)
	jenkins_id = models.IntegerField(default=0)
	status = models.IntegerField(default=0)

class Repo(models.Model):
	name = models.CharField(max_length=200, unique=True)
	bugs_project = models.SmallIntegerField(default=1)
	bugs_category = models.SmallIntegerField(default=2)
	svn_path = models.CharField(max_length=64)
	def __str__(self):
		return self.name


