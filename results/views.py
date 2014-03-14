from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views import generic
from django import forms
import json
import urllib.request
import urllib.parse
import re

from results.models import Result

from django.template.loader import add_to_builtins

add_to_builtins('results.tags')

@csrf_exempt
def submit(request):
	package = request.POST['package']
	repo = request.POST['repo']
	jenkins_id = request.POST['jenkins_id']
	status = request.POST['status']
	try:
		r = Result.objects.get(package=package, repo=repo)
	except Result.DoesNotExist:
		return HttpResponse("")
	r.jenkins_id = jenkins_id
	r.status = status
	r.save()
	return HttpResponse("")

@csrf_exempt
def add(request):
	package = request.POST['package']
	repo = request.POST['repo']
	try:
		r = Result.objects.get(package=package, repo=repo)
	except Result.DoesNotExist:
		r = Result(package=package, repo=repo)
		r.status = -1
		r.save()

	return HttpResponse("")

def load(request, repo, package):
	r = Result.objects.get(package=package, repo=repo)
	response = urllib.request.urlopen("https://www.archlinux.org/packages/"+r.repo+"/"+"x86_64"+"/"+r.package+"/json/")
	res = response.read().decode("utf-8")
	data = json.loads(res)
	if data['flag_date'] != None:
		r.flagged = True
		r.save()
	return HttpResponseRedirect('/results/');

def loadBug(request, repo, package):
	r = Result.objects.get(package=package, repo=repo)
	project = 0
	if repo == "community":
		project = 5
	response = urllib.request.urlopen("https://bugs.archlinux.org/index.php?string="+package+"&project="+str(project)+"&status%5B%5D=open&opened=klusark")
	res = response.read().decode("utf-8")
	m = re.search('/task/([0-9]+)', res)
	if m == None:
		return HttpResponse("no bug")
	r.bug_id = int(m.group(0)[6:])
	r.save()
	return HttpResponse("bug")


def buildPackage(repo, package):
	data = {}
	data['PACKAGE'] = package
	data['REPO'] = repo
	data['token'] = "BUILDTOKEN"
	d = urllib.parse.urlencode(data).encode('UTF-8')
	headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
	response = urllib.request.urlopen("http://127.0.0.1:8090/job/package/buildWithParameters", d)

def rebuild(request, repo, package):
	buildPackage(repo, package)
	return HttpResponseRedirect('/results/' + repo +"/" + package);

def rebuildFailed(request):
	objs = filterObjs(request.GET)
	for r in objs:
		buildPackage(r.repo, r.package)
	return HttpResponseRedirect('/results/');

def filterObjs(GET):
	objs = Result.objects.all();

	if ('repo' in GET):
		objs = objs.filter(repo = GET['repo'])
	if ('bug_id' in GET):
		objs = objs.filter(bug_id = GET['bug_id'])
	if ('package' in GET):
		objs = objs.filter(package = GET['package'])
	if ('status' in GET):
		objs = objs.filter(status = GET['status'])
	if ('flag' in GET):
		objs = objs.filter(flagged = GET['flag'])
	return objs

class IndexView(generic.ListView):
	template_name = 'index.html'
	context_object_name = 'results'

	def get_queryset(self):

		return filterObjs(self.request.GET)

class EditForm(forms.Form):
	bug_id = forms.IntegerField()

def edit(request, repo, package):
	r = Result.objects.get(package=package, repo=repo)
	if (request.method == 'POST'):
		form = EditForm(request.POST)
		if form.is_valid():
			r.bug_id = form.cleaned_data['bug_id']
			r.save()
			return HttpResponseRedirect('/results/' + repo +"/" + package);
	else:
		form = EditForm()
	return render(request, 'edit.html', {'r': r, 'form': form})

def PackageView(request, repo, package):
	r = Result.objects.get(package=package, repo=repo)
	return render(request, 'package.html', {'r': r})
