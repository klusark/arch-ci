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
from django.core.urlresolvers import reverse
from results.models import Result, Build, Repo
from results.tags import JenkinsURL
from django.db.models import Avg
from django.template.loader import add_to_builtins
from datetime import datetime
from django.forms import ModelForm

add_to_builtins('results.tags')

make_choice = lambda l: [(str(m), str(m)) for m in l]

class PackageSearchForm(forms.Form):
	repo = forms.MultipleChoiceField(required=False)
	arch = forms.MultipleChoiceField(required=False)
	name = forms.CharField(required=False)
	desc = forms.CharField(required=False)
	q = forms.CharField(required=False)
	sort = forms.CharField(required=False, widget=forms.HiddenInput())
	maintainer = forms.ChoiceField(required=False)
	packager = forms.ChoiceField(required=False)
	flagged = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['Flagged', 'Not Flagged']),
		required=False)
	status = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['Success', 'Failure', 'In progress', 'Removed']),
		required=False)
	reason = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['General', 'Check', 'Source', 'Depends']),
		required=False)
	bug = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['Yes', 'No']),
		required=False)
	page = forms.CharField(required=False)
	limit = forms.IntegerField(required=False)
	avg = forms.IntegerField(required=False)

	def __init__(self, *args, **kwargs):
		super(PackageSearchForm, self).__init__(*args, **kwargs)
		repos = Repo.objects.all()
		self.fields['repo'].choices = make_choice([repo.name for repo in repos])

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
	r.reason = 0
	if int(status) != 0:
		detectFailure(r)
	r.save()
	if int(status) < 2:
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
		rep = Repo.objects.get(name=repo)
		r = Result(package=package, repo=rep)
		r.status = -1
		r.save()

	return HttpResponse("")

def detect(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	detectFailure(r)

	return HttpResponse("")

def detectFailure(r):
	response = urllib.request.urlopen("%s/consoleText" % JenkinsURL(r.jenkins_id))
	res = response.read().decode("utf-8")
	if (res.find("A failure occurred in check") != -1):
		r.reason = 2
	elif (res.find("Could not download sources") != -1):
		r.reason = 3
	elif (res.find("failed to install missing dependencies") != -1):
		r.reason = 4
	elif (res.find("End-of-central-directory signature not found") != -1):
		r.reason = 5
	else:
		r.reason = 1
	r.save()


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
		r.bug_id = 0
		r.save()
		return HttpResponse("no bug")
	r.bug_id = int(m.group(0)[6:])
	r.save()
	return HttpResponse("bug")


def buildPackage(repo, package):
	rl = Result.objects.filter(package=package, repo__name=repo)
	rl = rl.annotate(a=Avg('build__length'))
	r = rl[0];
	data = {}
	data['PACKAGE'] = package
	data['REPO'] = repo
	data['token'] = "BUILDTOKEN"
	#if (r.a > 600):
	#	data['NODE'] = 'build1'
	d = urllib.parse.urlencode(data).encode('UTF-8')
	headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
	response = urllib.request.urlopen("http://127.0.0.1:8090/job/package/buildWithParameters", d)

def rebuild(request, repo, package):
	buildPackage(repo, package)
	return HttpResponseRedirect(reverse('package', args=(repo, package,)))

def rebuildFailed(request):
	form = PackageSearchForm(data=request.GET)
	if form.is_valid():
		objs = filterObjs(form)
		for r in objs:
			buildPackage(r.repo.name, r.package)
		return HttpResponse("OK\n");
	return HttpResponse("You messed up the form\n");

def filterObjs(form):
	objs = Result.objects.all();
	if form.cleaned_data['flagged'] == 'Flagged':
		objs = objs.filter(flagged = 1)
	elif form.cleaned_data['flagged'] == 'Not Flagged':
		objs = objs.filter(flagged = 0)

	if form.cleaned_data['repo']:
		objs = objs.filter(repo__name__in=form.cleaned_data['repo'])

	if form.cleaned_data['status'] == 'Success':
		objs = objs.filter(status = 0)
	elif form.cleaned_data['status'] == 'Failure':
		objs = objs.filter(status = 1)
	elif form.cleaned_data['status'] == 'In progress':
		objs = objs.filter(status = 2)
	elif form.cleaned_data['status'] == 'Removed':
		objs = objs.filter(status = 3)

	if form.cleaned_data['bug'] == 'Yes':
		objs = objs.filter(bug_id__gt = 0)
	elif form.cleaned_data['bug'] == 'No':
		objs = objs.filter(bug_id = 0)

	if form.cleaned_data['reason'] == 'General':
		objs = objs.filter(reason = 1)
	elif form.cleaned_data['reason'] == 'Check':
		objs = objs.filter(reason = 2)
	elif form.cleaned_data['reason'] == 'Source':
		objs = objs.filter(reason = 3)
	elif form.cleaned_data['reason'] == 'Depends':
		objs = objs.filter(reason = 4)

	if form.cleaned_data['avg'] != None:
		objs = objs.annotate(a=Avg('build__length')).filter(a__lte=int(form.cleaned_data['avg']))

	sort = form.cleaned_data['sort']
	sort_fields = ['last_built']
	allowed_sort = list(sort_fields) + ["-" + s for s in sort_fields]
	if sort in allowed_sort:
		objs = objs.order_by(sort)
	else:
		objs = objs.order_by('package')

	if form.cleaned_data['limit'] != None:
		objs = objs[:int(form.cleaned_data['limit'])]


	paginator = Paginator(objs, 50)
	page = form.cleaned_data['page']
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

	def get(self, request, *args, **kwargs):
		self.form = PackageSearchForm(data=request.GET)
		return super(IndexView, self).get(request, *args, **kwargs)

	def get_queryset(self):
		if self.form.is_valid():
			return filterObjs(self.form)
		return Result.objects.none()

	def get_context_data(self, **kwargs):
		context = super(IndexView, self).get_context_data(**kwargs)
		query_params = self.request.GET.copy()
		query_params.pop('page', None)
		context['current_query'] = query_params.urlencode()
		context['search_form'] = self.form
		return context

class EditForm(ModelForm):
	class Meta:
		model = Result
		fields = ['bug_id', 'flagged']

def edit(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	if (request.method == 'POST'):
		form = EditForm(request.POST, instance=r)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect(reverse('package', args=(repo, package,)))
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
	dir = "/var/git/%s/%s/trunk/" % (r.repo.svn_path, package)

	if not os.path.exists(dir):
		return HttpResponse("could not find package")

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
