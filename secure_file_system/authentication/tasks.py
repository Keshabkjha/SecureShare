from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext_lazy as _

@shared_task(bind=True, max_retries=3)
def send_verification_email_task(self, user_email, verification_url):
    """
    Celery task to send verification email asynchronously.
    """
    try:
        send_mail(
            _('Verify your email address'),
            _('Please click the following link to verify your email: {}').format(verification_url),
            settings.DEFAULT_FROM_EMAIL,
            [user_email],
            fail_silently=False,
        )
    except Exception as e:
        # Retry the task if it fails
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes
