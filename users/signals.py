from django.contrib.auth.models import Group
from allauth.account.signals import user_signed_up
from django.dispatch import receiver

@receiver(user_signed_up)
def assign_group(sender, request, user, **kwargs):
    common_user_group, created = Group.objects.get_or_create(name='Common Users')
    user.groups.add(common_user_group)
