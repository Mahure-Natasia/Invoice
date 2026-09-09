from .health import health
from django.contrib import admin
from django.urls import include, path
from billing import views
from billing.forms import LoginForm
from django.contrib.auth.views import LoginView

urlpatterns = [path('health/', health, name='health'), path('admin/', admin.site.urls), path('accounts/register/', views.register, name='register'),
               path('accounts/login/', LoginView.as_view(authentication_form=LoginForm), name='login'),
               path('accounts/', include('django.contrib.auth.urls')), path('', include('billing.urls'))]
