from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from notifications import views
router = DefaultRouter()
router.register('triggers', views.TriggerViewSet)
router.register('templates', views.TemplateViewSet)
router.register('deliveries', views.DeliveryViewSet, basename='delivery')
urlpatterns = [path('admin/', admin.site.urls), path('api/health/', views.health),
    path('api/config/', views.configuration), path('api/auth/login/', views.LoginView.as_view()),
    path('api/auth/logout/', views.LogoutView.as_view()), path('api/auth/me/', views.MeView.as_view()),
    path('api/push-subscriptions/', views.PushView.as_view()), path('api/', include(router.urls))]
