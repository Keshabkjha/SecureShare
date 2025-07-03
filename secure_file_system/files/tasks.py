from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.utils.translation import gettext_lazy as _

@shared_task(bind=True, max_retries=3)
def send_file_upload_notification(self, file_id, recipient_emails):
    """
    Celery task to send email notifications when a file is uploaded.
    
    Args:
        file_id: ID of the uploaded file
        recipient_emails: List of email addresses to notify
    """
    from .models import File
    from django.contrib.auth import get_user_model
    
    try:
        file_obj = File.objects.get(id=file_id)
        user_model = get_user_model()
        
        # Get the uploader's name
        uploader_name = f"{file_obj.uploaded_by.first_name} {file_obj.uploaded_by.last_name}".strip()
        if not uploader_name:
            uploader_name = file_obj.uploaded_by.email
            
        # Prepare email content
        subject = _('New File Uploaded: {}').format(file_obj.original_filename)
        message = _(
            'A new file has been uploaded by {uploader}.\n\n'
            'File Details:\n'
            'Name: {filename}\n'
            'Type: {file_type}\n'
            'Size: {size} bytes\n'
            'Uploaded at: {upload_time}\n\n'
            'You can access the file through the secure file sharing system.'
        ).format(
            uploader=uploader_name,
            filename=file_obj.original_filename,
            file_type=file_obj.get_file_type_display(),
            size=file_obj.file_size,
            upload_time=file_obj.created_at.strftime('%Y-%m-%d %H:%M:%S')
        )
        
        # Send email to each recipient
        for email in recipient_emails:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
    except Exception as e:
        # Retry the task if it fails
        self.retry(exc=e, countdown=60 * 5)  # Retry after 5 minutes
