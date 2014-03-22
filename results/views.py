from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views import generic
from django import forms
import json
import urllib.request
import urllib.parse
import urllib.error
import re
import zipfile
import os
import io
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from results.models import Result, Build
from django.db.models import Avg
from django.template.loader import add_to_builtins
from datetime import datetime
from django.forms import ModelForm

add_to_builtins('results.tags')

@csrf_exempt
def submit(request):
	package = request.POST['package']
	repo = request.POST['repo']
	jenkins_id = request.POST['jenkins_id']
	status = request.POST['status']
	try:
		r = Result.objects.get(package=package, repo__name=repo)
	except Result.DoesNotExist:
		return HttpResponse("")
	r.jenkins_id = jenkins_id
	r.status = status
	r.last_built = datetime.now()
	if int(status) != 0:
		detectFailure(r)
	r.save()
	if int(status) != 2:
		b = Build()
		b.package = r
		b.length = request.POST['time'];
		b.jenkins_id = request.POST['jenkins_id']
		b.status = status
		b.save()
	return HttpResponse("")

@csrf_exempt
def add(request):
	package = request.POST['package']
	repo = request.POST['repo']
	try:
		r = Result.objects.get(package=package, repo__name=repo)
	except Result.DoesNotExist:
		r = Result(package=package, repo=repo)
		r.status = -1
		r.save()

	return HttpResponse("")

def detectFailure(r):
	response = urllib.request.urlopen("http://162.243.149.218:8090/job/package/"+str(r.jenkins_id)+"/consoleText")
	res = response.read().decode("utf-8")
	r.check = False
	r.source = False
	if (res.find("A failure occurred in check") != -1):
		r.check = True
	#if (res.find("A failure occurred in build") != -1):
	#	r.build = True
	if (res.find("Could not download sources") != -1):
		r.source = True


def load(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	response = None
	try:
		response = urllib.request.urlopen("https://www.archlinux.org/packages/"+r.repo.name+"/"+"x86_64"+"/"+r.package+"/json/")
	except:
		response = urllib.request.urlopen("https://www.archlinux.org/packages/"+r.repo.name+"/"+"any"+"/"+r.package+"/json/")
	res = response.read().decode("utf-8")
	data = json.loads(res)
	if data['flag_date'] != None:
		r.flagged = True
		r.save()
		return HttpResponse('flag')
	else:
		r.flagged = False
		r.save()
		return HttpResponse('no flag')

def loadBug(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
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
	return HttpResponse("OK\n");

def filterObjs(GET):
	objs = Result.objects.all();
	if ('order_by' in GET):
		objs = objs.order_by(GET['order_by'])

	if 'avg' in GET:
		objs = objs.annotate(a=Avg('build__length')).filter(a__gte=1).order_by("a")
	if ('repo' in GET):
		objs = objs.filter(repo__name = GET['repo'])
	if ('bug_id' in GET):
		objs = objs.filter(bug_id = GET['bug_id'])
	if ('package' in GET):
		objs = objs.filter(package = GET['package'])
	if ('status' in GET):
		objs = objs.filter(status = GET['status'])
	if ('flag' in GET):
		objs = objs.filter(flagged = GET['flag'])
	if ('source' in GET):
		objs = objs.filter(source = GET['source'])
	if ('check' in GET):
		objs = objs.filter(check = GET['check'])
	if 'limit' in GET:
		objs = objs[:int(GET['limit'])]

	paginator = Paginator(objs, 50)
	page = GET.get('page')
	try:
		objs = paginator.page(page)
	except PageNotAnInteger:
		objs = paginator.page(1)
	except EmptyPage:
		objs = paginator.page(paginator.num_pages)

	return objs

class IndexView(generic.ListView):
	template_name = 'index.html'
	context_object_name = 'results'

	def get_queryset(self):

		return filterObjs(self.request.GET)

class EditForm(ModelForm):
	class Meta:
		model = Result
		fields = ['bug_id', 'flagged', 'source', 'check']

def edit(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	if (request.method == 'POST'):
		form = EditForm(request.POST, instance=r)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect('/results/' + r.repo.name +"/" + package);
	else:
		form = EditForm(instance=r)
	return render(request, 'edit.html', {'r': r, 'form': form})

def PackageView(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	build = Build.objects.all()
	build = build.filter(package=r)
	l = build.aggregate(Avg('length'))
	return render(request, 'package.html', {'r': r, 'avg': l['length__avg']})

def download(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	dir = "/var/abs/"+r.repo.name+"/"+package+"/"
	dir2 = "/var/git/%s/%s/trunk/" % (r.repo.svn_path, package)

	if os.path.exists(dir2):
		dir = dir2

	s = io.BytesIO()
	zf = zipfile.ZipFile(s, "w")
	output = ""
	for root, dirs, files in os.walk(dir):
		for file in files:
			zip_path = os.path.join(package, file)
			zf.write(dir + file, zip_path)
			output += file

	zf.close()
	resp = HttpResponse(s.getvalue(), mimetype = "application/x-zip-compressed")
	resp['Content-Disposition'] = 'attachment; filename=%s.zip' % package
	return resp
