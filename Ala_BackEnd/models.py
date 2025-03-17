from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    id = models.AutoField(primary_key=True)
    mobile_phone_number = models.CharField(max_length=15, unique=True, null=True, blank=True)
    Full_name = models.CharField(max_length=255, null=True, blank=True)
    bio = models.TextField(null=True, blank=True)
    profile_image_path = models.CharField(max_length=255, null=True, blank=True)
    # is_bot = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    username = models.CharField(max_length=255, null=True, blank=True, unique=True)
    is_block = models.BooleanField(default=False)
    which_social_media = models.CharField(max_length=30, default="site")
    chat_id = models.CharField(max_length=30, null=True)
    is_admin = models.BooleanField(default=False)
    premium_level = models.IntegerField(default=0)
    subscription_end = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'mobile_phone_number'
    REQUIRED_FIELDS = ['username']  # Add any other required fields if necessary

    def __str__(self):
        return self.username if self.username else self.mobile_phone_number

class Card(models.Model):
    id = models.AutoField(primary_key=True)
    content = models.TextField(unique=True)
    challenge = models.TextField()
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cards')
    created_at = models.DateTimeField(auto_now_add=True)
    like_count = models.IntegerField(default=0)

    def __str__(self):
        return self.content[:50]

class SavedCard(models.Model):
    id = models.AutoField(primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_cards')
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='saved_by_users')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'card')  # Prevents duplicate saves

    def __str__(self):
        return f"{self.user.username} saved {self.card.content[:30]}"

class Comment(models.Model):
    id = models.AutoField(primary_key=True)
    content = models.TextField()
    card = models.ForeignKey(Card, on_delete=models.CASCADE, related_name='comments')
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
    like_count = models.IntegerField(default=0)

    def __str__(self):
        return self.content[:50]

class CommentReply(models.Model):
    id = models.AutoField(primary_key=True)
    comment = models.ForeignKey(Comment, on_delete=models.CASCADE, related_name='replies')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comment_replies')
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    like_count = models.IntegerField(default=0)

    def __str__(self):
        return self.content[:50]

class CommentLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.ForeignKey('Comment', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'comment')

    def __str__(self):
        return f"{self.user.username} likes {self.comment.id}"

class CommentReplyLike(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    reply = models.ForeignKey('CommentReply', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'reply')

    def __str__(self):
        return f"{self.user.username} likes reply {self.reply.id}"

class Notification(models.Model):
    id = models.AutoField(primary_key=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255, null=True, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    related_entity = models.ForeignKey(Card, on_delete=models.SET_NULL, related_name='notifications', null=True)

    def __str__(self):
        return self.title if self.title else "Notification"


# class Event(models.Model):
#     id = models.AutoField(primary_key=True)
#     event_type = models.TextField()
#     event_data = models.JSONField()
#     created_at = models.DateTimeField(auto_now_add=True)
#
#     def __str__(self):
#         return self.event_type