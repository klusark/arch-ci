from django.conf.urls import patterns, include, url


from results import views

package_patterns = patterns('',
	url(r'^load_flag/$', views.load, name='load_flag'),
	url(r'^load_bug/$', views.loadBug, name='load_bug'),
	url(r'^edit/$', views.edit, name='edit'),
	url(r'^rebuild/$', views.rebuild, name='rebuild'),
	url(r'^download/$', views.download, name='download'),
	url(r'^detect/$', views.detect, name='detect'),
	url(r'^$', views.PackageView, name='package'),
)

urlpatterns = patterns('',
	url(r'^rebuild_failed/$', views.rebuildFailed),
	url(r'^add/$', views.add),
	url(r'^submit/$', views.submit),
	url(r'^(?P<repo>\w+)/(?P<package>[^ /]+)/', include(package_patterns)),
	url(r'^$', views.IndexView.as_view(), name='index'),
)
