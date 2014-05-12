from django.contrib import admin
from results.models import Result, Build, Repo

class ResultAdmin(admin.ModelAdmin):
	search_fields = ['package']

admin.site.register(Result, ResultAdmin)
admin.site.register(Repo)
admin.site.register(Build)

