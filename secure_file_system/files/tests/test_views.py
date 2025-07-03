import os
import tempfile
import uuid
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.cache import cache

from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from authentication.models import User, EmailVerificationToken
from files.models import File, FileShareLink


def create_test_file(filename, content='test content'):
    # Create a temporary file for testing
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=filename)
    temp_file.write(content.encode())
    temp_file.close()
    return temp_file


class FileUploadDownloadTests(APITestCase):
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
        
        # Create a test file
        self.test_file = create_test_file('test.docx')
        
        # Create a test file in the database
        with open(self.test_file.name, 'rb') as f:
            self.uploaded_file = File.objects.create(
                file=SimpleUploadedFile('test_upload.docx', f.read()),
                original_filename='test_upload.docx',
                file_type='DOCX',
                file_size=1024,
                uploaded_by=self.ops_user
            )
        
    def tearDown(self):
        # Clean up test files
        if os.path.exists(self.test_file.name):
            os.unlink(self.test_file.name)
        
        # Clean up uploaded files
        for file_obj in File.objects.all():
            if file_obj.file and os.path.exists(file_obj.file.path):
                os.remove(file_obj.file.path)
        
        # Clear cache
        cache.clear()
    
    def test_ops_user_can_upload_file(self):
        """Test that an operations user can upload a file."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.ops_token}')
        
        with open(self.test_file.name, 'rb') as file:
            response = self.client.post(
                reverse('files:file_upload'),
                {'file': file, 'description': 'Test file'},
                format='multipart'
            )
            
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(File.objects.get().uploaded_by, self.ops_user)
    
    def test_client_user_cannot_upload_file(self):
        """Test that a client user cannot upload a file."""
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client_token}')
        
        with open(self.test_file.name, 'rb') as file:
            response = self.client.post(
                reverse('files:file_upload'),
                {'file': file, 'description': 'Test file'},
                format='multipart'
            )
            
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_download_link(self):
        """Test that a user can get a download link for a file."""
        # Upload a file first
        file_obj = File.objects.create(
            file=self.test_file.name,
            original_filename='test.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.ops_user,
            description='Test file'
        )
        
        # Get download link as client user
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client_token}')
        response = self.client.get(
            reverse('files:get_download_link', kwargs={'id': str(file_obj.id)})
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('download-link', response.data)
        self.assertIn('message', response.data)
        self.assertEqual(response.data['message'], 'success')
    
    def test_download_file_with_token(self):
        """Test that a file can be downloaded with a valid token."""
        # Create a file and share link
        file_obj = File.objects.create(
            file=self.test_file.name,
            original_filename='test.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.ops_user,
            description='Test file'
        )
        
        share_link = FileShareLink.objects.create(
            file=file_obj,
            created_by=self.ops_user,
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        # Download the file using the token
        response = self.client.get(
            reverse('files:secure_file_download', kwargs={'id': str(file_obj.id)}),
            {'token': str(share_link.token)}
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document')
        self.assertIn('attachment', response['Content-Disposition'])


class EmailVerificationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=False
        )
        self.verification_token = EmailVerificationToken.objects.create(user=self.user)
    
    def test_verify_email_success(self):
        """Test that email verification works with a valid token."""
        response = self.client.post(
            reverse('auth:verify-email'),
            {'token': str(self.verification_token.token)},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.is_verified)
    
    def test_verify_email_invalid_token(self):
        """Test that email verification fails with an invalid token."""
        response = self.client.post(
            reverse('auth:verify-email'),
            {'token': 'invalid-token'},
            format='json'
        )
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertFalse(self.user.is_verified)


class FileAccessControlTests(APITestCase):
    def setUp(self):
        # Create test users
        self.ops_user = User.objects.create_user(
            email='ops@example.com',
            password='testpass123',
            user_type=User.UserType.OPERATIONS,
            is_verified=True
        )
        self.client_user1 = User.objects.create_user(
            email='client1@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=True
        )
        self.client_user2 = User.objects.create_user(
            email='client2@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=True
        )
        
        # Create tokens for authentication
        self.ops_token = str(RefreshToken.for_user(self.ops_user).access_token)
        self.client1_token = str(RefreshToken.for_user(self.client_user1).access_token)
        self.client2_token = str(RefreshToken.for_user(self.client_user2).access_token)
        
        # Create a test file
        self.test_file = create_test_file('test.docx')
        
        # Upload a file as ops user
        self.file_obj = File.objects.create(
            file=self.test_file.name,
            original_filename='test.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.ops_user,
            description='Test file'
        )
    
    def test_client_can_list_own_files(self):
        """Test that a client can list their own files."""
        # Create a file for client1
        client1_file = File.objects.create(
            file=self.test_file.name,
            original_filename='client1_file.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.client_user1,
            description='Client 1 file'
        )
        
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client1_token}')
        response = self.client.get(reverse('files:file_list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['id'], str(client1_file.id))
    
    def test_client_cannot_access_other_client_files(self):
        """Test that a client cannot access files uploaded by another client."""
        # Create a file for client1
        client1_file = File.objects.create(
            file=self.test_file.name,
            original_filename='client1_file.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.client_user1,
            description='Client 1 file'
        )
        
        # Try to access client1's file as client2
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.client2_token}')
        response = self.client.get(
            reverse('files:file_detail', kwargs={'id': str(client1_file.id)})
        )
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_ops_can_access_all_files(self):
        """Test that an operations user can access all files."""
        # Create files for both clients
        client1_file = File.objects.create(
            file=self.test_file.name,
            original_filename='client1_file.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.client_user1,
            description='Client 1 file'
        )
        
        client2_file = File.objects.create(
            file=self.test_file.name,
            original_filename='client2_file.docx',
            file_type='DOCX',
            file_size=1234,
            uploaded_by=self.client_user2,
            description='Client 2 file'
        )
        
        # Access files as ops user
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.ops_token}')
        response = self.client.get(reverse('files:file_list'))
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 3)  # Includes the file uploaded in setUp
        
        # Check access to individual files
        response1 = self.client.get(
            reverse('files:file_detail', kwargs={'id': str(client1_file.id)})
        )
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        
        response2 = self.client.get(
            reverse('files:file_detail', kwargs={'id': str(client2_file.id)})
        )
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
