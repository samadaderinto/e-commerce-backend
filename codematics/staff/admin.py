from django.contrib import admin

from staff.models import BlogPost, Blog

# Register your models here.

admin.site.register(BlogPost)
admin.site.register(Blog)