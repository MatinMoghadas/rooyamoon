from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Comment, SavedCard, Card


@receiver([post_save, post_delete], sender=Comment)
def update_comment_count(sender, instance, **kwargs):
    card = instance.card
    card.comment_count = card.comments.count()  # count related comments
    card.save(update_fields=['comment_count'])


@receiver([post_save, post_delete], sender=SavedCard)
def update_saved_count(sender, instance, **kwargs):
    card = instance.card
    card.saved_count = card.saved_by_users.count()  # count related saved cards
    card.save(update_fields=['saved_count'])
