# products/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Головна сторінка з формою
    path('', views.home_view, name='home'),
    path('p/<int:pk>/', views.product_detail, name='product_detail'),
    
    # HTMX-ендпоінт для тестування парсингу посилання в реальному часі
    path('test-parse/', views.test_parse_product, name='test_parse'),
]