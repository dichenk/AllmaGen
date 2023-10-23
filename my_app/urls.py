from django.urls import path
from . import views


urlpatterns = [
    path('', views.main_page),
    path('ctrChart/', views.ctrChart, name='get_ctr_data')
]