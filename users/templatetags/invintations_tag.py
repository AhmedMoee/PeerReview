from django import template
from users.models import ProjectInvitation

register = template.Library()

@register.inclusion_tag('myapp/pending_invitations_count.html', takes_context=True)
def pending_invites_count(context):
    request = context['request']
    if request.user.is_authenticated:  # Ensure the user is logged in
        pending_count = ProjectInvitation.objects.filter(
            invited_user=request.user,
            status='PENDING'
        ).count()
    else:
        pending_count = 0

    return {'pending_invitations_count': pending_count}
