import os
import secrets
import string
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()

class Command(BaseCommand):
    help = 'Create a superuser with a secure random password'

    def add_arguments(self, parser):
        parser.add_argument('--email', help="Admin user's email")
        parser.add_argument('--password', help="Admin user's password (if not provided, will generate one)")
        parser.add_argument('--first-name', default='Admin', help="Admin user's first name")
        parser.add_argument('--last-name', default='User', help="Admin user's last name")

    def handle(self, *args, **options):
        email = options['email']
        
        if not email:
            email = input('Email address: ')
        
        # Check if user already exists
        if User.objects.filter(email=email).exists():
            self.stdout.write(self.style.WARNING(f'User with email {email} already exists.'))
            return
        
        # Generate a secure password if not provided
        password = options['password']
        if not password:
            alphabet = string.ascii_letters + string.digits + '!@#$%^&*()_+=-'
            password = ''.join(secrets.choice(alphabet) for _ in range(16))
        
        try:
            user = User.objects.create_superuser(
                email=email,
                password=password,
                first_name=options['first_name'],
                last_name=options['last_name'],
                user_type='OPERATIONS',
                is_verified=True
            )
            
            self.stdout.write(self.style.SUCCESS('Superuser created successfully!'))
            self.stdout.write(self.style.SUCCESS(f'Email: {email}'))
            self.stdout.write(self.style.SUCCESS(f'Password: {password}'))
            self.stdout.write(self.style.WARNING(
                'Please change this password after first login!'))
            
        except IntegrityError as e:
            raise CommandError(f'Could not create superuser: {e}')
