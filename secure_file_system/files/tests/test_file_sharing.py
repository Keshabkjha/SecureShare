import os
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import User
from files.models import File, FileShareLink


class FileSharingTests(APITestCase):
    def setUp(self):
        # Clear cache
        cache.clear()
        
        # Create test users
        self.ops_user = User.objects.create_user(
            email='ops@example.com',
            password='testpass123',
            user_type=User.UserType.OPERATIONS,
            is_verified=True,
            first_name='Ops',
            last_name='User'
        )
        self.client_user = User.objects.create_user(
            email='client@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=True,
            first_name='Client',
            last_name='User'
        )
        
        # Create tokens for authentication
        self.ops_token = str(RefreshToken.for_user(self.ops_user).access_token)
        self.client_token = str(RefreshToken.for_user(self.client_user).access_token)
        
        # Create a test file in the database
        test_content = b'This is a test file content'
        self.test_file = SimpleUploadedFile(
            'test_upload.docx',
            test_content,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        self.uploaded_file = File.objects.create(
            file=self.test_file,
            original_filename='test_upload.docx',
            file_type='DOCX',
            file_size=len(test_content),
            uploaded_by=self.ops_user
        )
    
    def tearDown(self):
        # Clean up uploaded files
        if hasattr(self, 'uploaded_file') and self.uploaded_file.file:
            if os.path.exists(self.uploaded_file.file.path):
                os.remove(self.uploaded_file.file.path)
        
        # Clear cache
        cache.clear()
    
    def test_secure_download(self):
        """Test secure file download with token authentication."""
        # Generate a secure download URL
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client_token}')
        response = self.client.get(
            reverse('file-download', kwargs={'pk': self.uploaded_file.id})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('download_url', response.data)
        
        # Extract the token from the URL
        download_url = response.data['download_url']
        token = download_url.split('token=')[1]
        
        # Test downloading with the token
        response = self.client.get(download_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Test downloading with an invalid token
        invalid_url = download_url.replace(token, 'invalid-token')
        response = self.client.get(invalid_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    @patch('files.tasks.send_file_upload_notification.delay')
    def test_file_upload_notification(self, mock_notification):
        """Test that file upload triggers a notification."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.ops_token}')
        
        test_content = b'New test file content'
        test_file = SimpleUploadedFile(
            'new_test_upload.docx',
            test_content,
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        data = {
            'file': test_file,
            'description': 'Test file for notification'
        }
        
        response = self.client.post(
            reverse('file-upload'),
            data,
            format='multipart'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(mock_notification.called)
    
    def test_file_share_link_creation(self):
        """Test creating a shareable link for a file."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.ops_token}')
        
        # Create a share link
        data = {
            'file': self.uploaded_file.id,
            'expires_at': (timezone.now() + timedelta(days=7)).isoformat(),
            'max_downloads': 5
        }
        
        response = self.client.post(
            reverse('filesharelink-list'),
            data,
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        
        # Test accessing the file with the share link
        share_token = response.data['token']
        response = self.client.get(
            reverse('file-share-download', kwargs={'token': share_token})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
    
    def test_share_link_expiration(self):
        """Test that share links expire after the specified time."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.ops_token}')
        
        # Create a share link that expires in 1 second
        data = {
            'file': self.uploaded_file.id,
            'expires_at': (timezone.now() + timedelta(seconds=1)).isoformat(),
            'max_downloads': 5
        }
        
        response = self.client.post(
            reverse('filesharelink-list'),
            data,
            format='json'
        )
        
        share_token = response.data['token']
        
        # Wait for the token to expire
        import time
        time.sleep(2)
        
        # Try to access the file after expiration
        response = self.client.get(
            reverse('file-share-download', kwargs={'token': share_token})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
