from django.contrib import admin
from Ala_BackEnd.models import  (User, Card, Comment, Notification,
                                 #CommentReply,
                                 SavedCard, CommentLike
                                 #, CommentReplyLike
                                )
# # from django.contrib.auth.admin import UserAdmin
# from .models import User  # Import your custom User model
# # Register your models here.
#
# # class CustomUserAdmin(UserAdmin):
# #     list_display = ('mobile_phone_number', 'first_name', 'last_name', 'is_staff', 'is_active')
# #     search_fields = ('mobile_phone_number', 'first_name', 'last_name')
# #     ordering = ('mobile_phone_number',)
# #     fieldsets = (
# #         (None, {'fields': ('mobile_phone_number', 'password')}),
# #         ('Personal Info', {'fields': ('first_name', 'last_name', 'bio', 'profile_image_path')}),
# #         ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
# #         ('Important Dates', {'fields': ('last_login',)}),
# #     )
# #     add_fieldsets = (
# #         (None, {
# #             'classes': ('wide',),
# #             'fields': ('mobile_phone_number', 'password1', 'password2', 'is_staff', 'is_superuser'),
# #         }),
# #     )
# #
# # # Register the custom user model
# # # Register each model with the admin panel
# # admin.site.register(User, CustomUserAdmin)
admin.site.register(User)
admin.site.register(Card)
admin.site.register(Comment)
admin.site.register(Notification)
# admin.site.register(CommentReply)
admin.site.register(SavedCard)
admin.site.register(CommentLike)
# admin.site.register(CommentReplyLike)
# admin.site.register(FCMToken)
