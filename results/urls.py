from django.conf.urls import patterns, include, url


from results import views

package_patterns = patterns('',
	url(r'^load/$', views.load, name='load'),
	url(r'^load_bug/$', views.loadBug, name='loadBug'),
	url(r'^edit/$', views.edit, name='edit'),
	url(r'^rebuild/$', views.rebuild, name='rebuild'),
	url(r'^$', views.PackageView, name='package'),
)

urlpatterns = patterns('',
	url(r'^rebuild_failed/$', views.rebuildFailed),
	url(r'^add/$', views.add),
	url(r'^submit/$', views.submit),
	url(r'^(?P<repo>\w+)/(?P<package>[^ /]+)/', include(package_patterns)),
	url(r'^$', views.IndexView.as_view(), name='index'),
)