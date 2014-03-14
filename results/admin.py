from django.contrib import admin
from results.models import Result

class ResultAdmin(admin.ModelAdmin):
	search_fields = ['package']

admin.site.register(Result, ResultAdmin)

