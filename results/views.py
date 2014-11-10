import codecs
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime

from django import forms
from django.contrib.auth.decorators import login_required
from django.core.files import File
from django.core.urlresolvers import reverse
from django.db.models import Avg
from django.forms import ModelForm
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, render
from django.template.base import add_to_builtins
from django.views import generic
from django.views.decorators.csrf import csrf_exempt
from django.core.serializers.json import DjangoJSONEncoder

from results.models import Build, Repo, Result
from results.tags import JenkinsURL, Status, Reason

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
		choices=[('', 'All')] + make_choice(['Success', 'Failure', 'In progress', 'Removed', 'Unbuilt']),
		required=False)
	reason = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['General', 'Check', 'Source', 'Hash', 'Depends']),
		required=False)
	bug = forms.ChoiceField(
		choices=[('', 'All')] + make_choice(['Yes', 'No']),
		required=False)
	page = forms.CharField(required=False)
	limit = forms.IntegerField(required=False)
	avg_max = forms.IntegerField(required=False)
	avg_min = forms.IntegerField(required=False)
	new_fail = forms.IntegerField(required=False)

	def __init__(self, *args, **kwargs):
		super(PackageSearchForm, self).__init__(*args, **kwargs)
		repos = Repo.objects.all()
		self.fields['repo'].choices = make_choice([repo.name for repo in repos])

@csrf_exempt
def submit(request):
#	if get_client_ip(request) != "127.0.0.1" and not request.user.is_authenticated():
#		return HttpResponse("NO AUTH\n");
	package = request.POST['package']
	repo = request.POST['repo']
	jenkins_id = request.POST['jenkins_id']
	status = int(request.POST['status'])
	if status == 255:
		status = 1
	try:
		r = Result.objects.get(package=package, repo__name=repo)
	except Result.DoesNotExist:
		return HttpResponse("")
	r.jenkins_id = jenkins_id
	r.status = status
	r.last_built = datetime.now()
	r.reason = 0
	r.new_fail = False
	if r.status == 1:
		builds = Build.objects.filter(package=r).order_by('-time')
		if len(builds) and builds[0].status == 0:
			r.new_fail = True
	r.save()
	if r.status != 0:
		detectFailure(r)
	if r.status != 2:
		b = Build()
		b.package = r
		b.length = request.POST['time'];
		b.jenkins_id = request.POST['jenkins_id']
		b.status = status
		b.reason = r.reason
		response = urllib.request.urlopen("%s/consoleText" % JenkinsURL(r.jenkins_id))
		res = response.read()
		b.log = codecs.encode(res, 'bz2')
		#if 'size' in request.POST and request.POST['size'] != None and request.POST['size'] != "":
		#	b.size = request.POST['size']
		b.save()
	return HttpResponse("OK\n")

@csrf_exempt
def add(request):
#	if get_client_ip(request) != "162.243.149.218":
#	return HttpResponse("NO AUTH\n");
	package = request.POST['package']
	repo = request.POST['repo']
	try:
		r = Result.objects.get(package=package, repo__name=repo)
	except Result.DoesNotExist:
		rep = Repo.objects.get(name=repo)
		r = Result(package=package, repo=rep)
		r.status = -1
		r.save()

	return HttpResponse("OK")

def detect(request, repo, package):
	r = Result.objects.get(package=package, repo__name=repo)
	detectFailure(r)

	return HttpResponse("")

def outputLog(b):
	return HttpResponse("<pre>"+codecs.decode(b.log,'bz2').decode('utf-8')+"</pre>")


def GetLog(request, repo, package):
	r = get_object_or_404(Result, package=package, repo__name=repo)

	b = Build.objects.filter(package=r).latest('time')

	return outputLog(b)


def GetSpecificLog(request, repo, package, build):
	r = get_object_or_404(Result, package=package, repo__name=repo)
	b = get_object_or_404(Build, package=r, jenkins_id=build)
	return outputLog(b)

def detectFailure(r):
	response = urllib.request.urlopen("%s/consoleText" % JenkinsURL(r.jenkins_id))
	res = response.read().decode("utf-8")
	if (res.find("A failure occurred in check") != -1):
		r.reason = 2
	elif (res.find("One or more files did not pass the validity check!") != -1):
		r.reason = 6
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
	processJSON(data)
	if data['flag_date'] != None:
		return HttpResponse('flag')
	else:
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
	#if (r.a == None or r.a > 600):
	#	data['NODE'] = 'build1'
	d = urllib.parse.urlencode(data).encode('UTF-8')
	headers = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
	response = urllib.request.urlopen("http://127.0.0.1:8090/job/package/buildWithParameters", d)

@login_required()
def rebuild(request, repo, package):
	buildPackage(repo, package)
	return HttpResponseRedirect(reverse('package', args=(repo, package,)))

def get_client_ip(request):
	x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
	if x_forwarded_for:
		ip = x_forwarded_for.split(',')[0]
	else:
		ip = request.META.get('REMOTE_ADDR')
	return ip

def rebuildList(request):
#	if get_client_ip(request) != "127.0.0.1" and not request.user.is_authenticated():
#		return HttpResponse("NO AUTH\n");
	form = PackageSearchForm(data=request.GET)
	if form.is_valid():
		objs = Result.objects.all();
		objs = filterObjs(form, objs)
		for r in objs:
			buildPackage(r.repo.name, r.package)
		return HttpResponse(" OK\n");
	return HttpResponse("You messed up the form\n");

def filterObjs(form, objs):
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
	elif form.cleaned_data['status'] == 'Unbuilt':
		objs = objs.filter(status = -1)

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
	elif form.cleaned_data['reason'] == 'Hash':
		objs = objs.filter(reason = 6)
	elif form.cleaned_data['reason'] == 'Depends':
		objs = objs.filter(reason = 4)

	if form.cleaned_data['avg_max'] != None or form.cleaned_data['avg_min'] != None or form.cleaned_data['sort'] == 'avg'or form.cleaned_data['sort'] == '-avg':
		objs = objs.annotate(avg=Avg('build__length'))

	if form.cleaned_data['avg_max'] != None:
		objs = objs.filter(avg__lte=int(form.cleaned_data['avg_max']))

	if form.cleaned_data['avg_min'] != None:
		objs = objs.filter(avg__gte=int(form.cleaned_data['avg_min']))

	if form.cleaned_data['q'] != None:
		objs = objs.filter(package__icontains=form.cleaned_data['q']);

	if form.cleaned_data['new_fail'] != None:
		objs = objs.filter(new_fail=True)

	sort = form.cleaned_data['sort']
	sort_fields = ['last_built', 'avg', 'package', 'repo']
	allowed_sort = list(sort_fields) + ["-" + s for s in sort_fields]
	if sort in allowed_sort:
		objs = objs.order_by(sort)
	else:
		objs = objs.order_by('-last_built')

	limit = 100
	if form.cleaned_data['limit'] != None:
		objs = objs[:int(form.cleaned_data['limit'])]
		limit = int(form.cleaned_data['limit'])


	return objs

class IndexView(generic.ListView):
	template_name = 'index.html'

	paginate_by = 50

	def get(self, request, *args, **kwargs):
		self.form = PackageSearchForm(data=request.GET)
		return super(IndexView, self).get(request, *args, **kwargs)

	def get_queryset(self):
		if self.form.is_valid():
			packages = Result.objects.select_related()
			return filterObjs(self.form, packages)
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
		fields = ['bug_id', 'flagged', 'reason']

@login_required()
def edit(request, repo, package):
	r = get_object_or_404(Result, package=package, repo__name=repo)
	if (request.method == 'POST'):
		form = EditForm(request.POST, instance=r)
		if form.is_valid():
			form.save()
			return HttpResponseRedirect(reverse('package', args=(repo, package,)))
	else:
		form = EditForm(instance=r)
	return render(request, 'edit.html', {'r': r, 'form': form})

def PackageView(request, repo, package):
	r = get_object_or_404(Result, package=package, repo__name=repo)
	b = Build.objects.filter(package=r).order_by("id")
	l = b.aggregate(Avg('length'))
	return render(request, 'package.html', {'r': r, 'builds': b, 'avg': l['length__avg']})

def download(request, repo, package):
	r = get_object_or_404(Result, package=package, repo__name=repo)
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
	resp = HttpResponse(s.getvalue())
	resp['Content-Disposition'] = 'attachment; filename=%s.zip' % package
	return resp

def processJSON(data):
	try:
		r = Result.objects.get(package=data["pkgname"], repo__name=data["repo"])
		if data['flag_date'] != None:
			r.flagged = True
		else:
			r.flagged = False
		r.save()
	except Result.DoesNotExist:
		return

@login_required()
def loadJSON(request):
	response = urllib.request.urlopen("https://www.archlinux.org/packages/search/json/?arch=any&arch=x86_64&repo=Community&repo=Core&repo=Extra&flagged=Flagged")
	res = response.read().decode("utf-8")
	data = json.loads(res)

	objs = Result.objects.all().update(flagged=False)

	for result in data["results"]:
		processJSON(result)

	return HttpResponse("done")


class PackageJSONEncoder(DjangoJSONEncoder):
	pkg_attributes = ['package', 'last_built', 'status', 'reason']

	def default(self, obj):
		if hasattr(obj, '__iter__'):
			# mainly for queryset serialization
			return list(obj)
		if isinstance(obj, Result):
			data = {attr: getattr(obj, attr) for attr in self.pkg_attributes}
			data['status'] = Status(data['status'])
			data['reason'] = Reason(data['reason'])
			return data
		return super(PackageJSONEncoder, self).default(obj)

def search_json(request):
	limit = 250

	container = {
		'version': 2,
		'limit': limit,
		'valid': False,
		'results': [],
	}

	if request.GET:
		form = PackageSearchForm(data=request.GET)
		if form.is_valid():
			objs = Result.objects.all();
			objs = filterObjs(form, objs)
			container['results'] = objs
			container['valid'] = True

	to_json = json.dumps(container, ensure_ascii=False, cls=PackageJSONEncoder)
	return HttpResponse(to_json, content_type='application/json')


def pkg_json(request, repo, package):
	r = get_object_or_404(Result, package=package, repo__name=repo)

	to_json = json.dumps(r, ensure_ascii=False, cls=PackageJSONEncoder)
	return HttpResponse(to_json, content_type='application/json')
