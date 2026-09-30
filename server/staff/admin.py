from django.contrib import admin

from staff.models import Post, Content, Comment

# Register your models here.

admin.site.register(Post)
admin.site.register(Content)
admin.site.register(Comment)
