from django.urls import path
from . import views

urlpatterns = [path('', views.dashboard, name='dashboard'),
    path('api/state/', views.state, name='state'),
    path('api/customers/', views.customers, name='customers'),
    path('api/customers/<int:pk>/', views.customer, name='customer-detail'),
    path('api/invoices/', views.invoices, name='invoices'),
    path('api/invoices/<int:pk>/', views.invoice, name='invoice-detail'),
    path('api/invoices/<int:pk>/<str:action>/', views.invoice_action, name='invoice-action'),
    path('api/payments/', views.payments, name='payments'),
    path('api/reports/', views.reports, name='reports'),
    path('api/profile/', views.profile, name='profile'),
    path('api/settings/', views.settings, name='settings'),
    path('business/logo/', views.logo, name='business-logo'),
    path('invoices/<int:pk>/print/', views.print_invoice, name='invoice-print')]
