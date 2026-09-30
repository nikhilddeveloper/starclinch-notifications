from django.contrib import admin
from .models import Profile
# Templates are managed through the application panel, where validation and approval rules apply.
admin.site.register(Profile)
