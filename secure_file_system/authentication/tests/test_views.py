import json
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()

class AuthenticationTests(APITestCase):
    def setUp(self):
        self.client = APIClient()
        self.ops_user = User.objects.create_user(
            email='ops@example.com',
            password='testpass123',
            user_type=User.UserType.OPERATIONS,
            is_verified=True
        )
        self.client_user = User.objects.create_user(
            email='client@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=True
        )
        self.unverified_user = User.objects.create_user(
            email='unverified@example.com',
            password='testpass123',
            user_type=User.UserType.CLIENT,
            is_verified=False
        )

    def test_ops_user_login(self):
        """Test Ops user can login"""
        url = reverse('token_obtain_pair')
        data = {'email': 'ops@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_client_user_login(self):
        """Test Client user can login"""
        url = reverse('token_obtain_pair')
        data = {'email': 'client@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_unverified_user_login_fails(self):
        """Test unverified user cannot login"""
        url = reverse('token_obtain_pair')
        data = {'email': 'unverified@example.com', 'password': 'testpass123'}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_new_user(self):
        """Test new user registration"""
        url = reverse('user-register')
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'password2': 'newpass123',
            'user_type': 'CLIENT'
        }
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.count(), 4)  # 3 in setUp + 1 new

    def test_refresh_token(self):
        """Test token refresh"""
        refresh = RefreshToken.for_user(self.client_user)
        url = reverse('token_refresh')
        data = {'refresh': str(refresh)}
        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
