from django.db import models
import codecs
from south.modelsinspector import add_introspection_rules

add_introspection_rules([], ["^results\.models\.LogField"])

class LogField(models.Field, metaclass=models.SubfieldBase):
	def db_type(self, connection):
		return 'bytea'
	#def to_python(self, value):
	#	if (value):
	#		return codecs.decode(value, 'bz2').decode('utf-8')
	#	else:
	#		return self.get_default()
	#def get_prep_value(self, value):
	#	return codecs.encode(value.encode('utf-8'), 'bz2')

class Result(models.Model):
	package = models.CharField(max_length=200, db_index=True)
	repo = models.ForeignKey('Repo')
	jenkins_id = models.IntegerField(default=0)
	status = models.IntegerField(default=0)
	last_built = models.DateTimeField(auto_now_add = True, db_index=True)
	bug_id = models.IntegerField(default=0)
	flagged = models.BooleanField(default=False)
	arch = models.CharField(max_length=200)
	reason = models.IntegerField(default=0)
	new_fail = models.BooleanField(default=False)
	maintainer = models.CharField(max_length=200, default='')
	def __str__(self):
		return self.package

class Build(models.Model):
	package = models.ForeignKey('Result')
	length = models.IntegerField(default=0)
	time = models.DateTimeField(auto_now_add = True)
	jenkins_id = models.IntegerField(default=0)
	status = models.IntegerField(default=0)
	reason = models.IntegerField(default=0)
	data = models.IntegerField(default=0)
	size = models.IntegerField(default=0)
	log = LogField(null=True)


class Repo(models.Model):
	name = models.CharField(max_length=200, unique=True)
	bugs_project = models.SmallIntegerField(default=1)
	bugs_category = models.SmallIntegerField(default=2)
	svn_path = models.CharField(max_length=64)
	def __str__(self):
		return self.name


