import os
import tempfile
from datetime import timedelta
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from files.models import File, FileShareLink

User = get_user_model()

class BaseTestCase(APITestCase):
    def setUp(self):
        # Create test users
        self.operations_user = User.objects.create_user(
            email='operations@example.com',
            password='testpass123',
            user_type='OPERATIONS',
            is_verified=True
        )
        self.client_user = User.objects.create_user(
            email='client@example.com',
            password='testpass123',
            user_type='CLIENT',
            is_verified=True
        )
        
        # Create a test file
        self.test_file = SimpleUploadedFile(
            'test.docx',
            b'Test file content',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Create a file for testing
        self.file = File.objects.create(
            original_filename='test.docx',
            file_type='DOCX',
            file_size=1024,
            uploaded_by=self.operations_user
        )
        
        # Create a share link
        self.share_link = FileShareLink.objects.create(
            file=self.file,
            created_by=self.operations_user,
            expires_at=timezone.now() + timedelta(days=7)
        )


class AuthenticationTests(BaseTestCase):
    def test_client_registration(self):
        """Test client registration with email verification"""
        url = reverse('client-register')
        data = {
            'email': 'newclient@example.com',
            'password': 'testpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 3)  # 2 from setUp + 1 new
        self.assertFalse(User.objects.get(email='newclient@example.com').is_verified)

    def test_login(self):
        """Test user login and token generation"""
        url = reverse('token_obtain_pair')
        data = {
            'email': 'client@example.com',
            'password': 'testpass123'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)


class FileTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Get JWT token for operations user
        refresh = RefreshToken.for_user(self.operations_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_upload_file(self):
        """Test file upload by operations user"""
        url = reverse('file-list')
        with tempfile.NamedTemporaryFile(suffix='.docx') as tmp:
            tmp.write(b'Test file content')
            tmp.seek(0)
            data = {'file': tmp}
            response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 2)  # 1 from setUp + 1 new
    
    def test_upload_invalid_file_type(self):
        """Test uploading invalid file type"""
        url = reverse('file-list')
        with tempfile.NamedTemporaryFile(suffix='.pdf') as tmp:
            tmp.write(b'Test PDF content')
            tmp.seek(0)
            data = {'file': tmp}
            response = self.client.post(url, data, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ShareLinkTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Get JWT token for operations user
        refresh = RefreshToken.for_user(self.operations_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_create_share_link(self):
        """Test creating a share link"""
        url = reverse('file-share', kwargs={'pk': self.file.pk})
        response = self.client.post(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(FileShareLink.objects.count(), 2)  # 1 from setUp + 1 new
    
    def test_download_shared_file(self):
        """Test downloading a file using a share link"""
        # First, create a share link
        share_link = FileShareLink.objects.create(
            file=self.file,
            created_by=self.operations_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Test download with share token
        client = APIClient()
        url = reverse('share-link-download', kwargs={'token': str(share_link.token)})
        response = client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Disposition'], f'attachment; filename="{self.file.original_filename}"')


class ClientFileTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        # Get JWT token for client user
        refresh = RefreshToken.for_user(self.client_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
    
    def test_list_available_files(self):
        """Test client can list files shared with them"""
        url = reverse('client-file-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)  # Should see the file from setUp


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class FileCleanupTest(TestCase):
    """Test file cleanup on model deletion"""
    def test_file_deletion(self):
        """Test that file is deleted from filesystem when model is deleted"""
        user = User.objects.create_user(
            email='testcleanup@example.com',
            password='testpass123',
            user_type='OPERATIONS'
        )
        
        # Create a test file
        test_file = SimpleUploadedFile(
            'test_cleanup.docx',
            b'Test cleanup content',
            content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        )
        
        # Create file record
        file_obj = File.objects.create(
            original_filename='test_cleanup.docx',
            file=test_file,
            file_type='DOCX',
            file_size=1024,
            uploaded_by=user
        )
        
        # Get file path
        file_path = file_obj.file.path
        
        # Verify file exists
        self.assertTrue(os.path.exists(file_path))
        
        # Delete the file record
        file_obj.delete()
        
        # Verify file is deleted
        self.assertFalse(os.path.exists(file_path))
