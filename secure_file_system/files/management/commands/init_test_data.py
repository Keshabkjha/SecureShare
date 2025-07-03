import os
import random
import string
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files import File
from django.conf import settings
from faker import Faker

from files.models import File, FileShareLink

User = get_user_model()
fake = Faker()

class Command(BaseCommand):
    help = 'Initialize test data for development and testing'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=5, help='Number of test users to create')
        parser.add_argument('--files', type=int, default=20, help='Number of test files to create')
        parser.add_argument('--share-links', type=int, default=10, help='Number of test share links to create')

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to initialize test data...'))
        
        # Create test users
        users = self.create_test_users(options['users'])
        
        # Create test files
        files = self.create_test_files(users, options['files'])
        
        # Create test share links
        self.create_test_share_links(users, files, options['share_links'])
        
        self.stdout.write(self.style.SUCCESS('Successfully initialized test data!'))
    
    def create_test_users(self, count):
        self.stdout.write(f'Creating {count} test users...')
        users = []
        
        # Create operations users (30% of total)
        operations_count = max(1, int(count * 0.3))
        for i in range(operations_count):
            user = User.objects.create_user(
                email=f'operations{i+1}@example.com',
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type='OPERATIONS',
                is_verified=True
            )
            users.append(user)
            self.stdout.write(f'Created operations user: {user.email} (password: testpass123)')
        
        # Create client users (remaining 70%)
        client_count = count - operations_count
        for i in range(client_count):
            user = User.objects.create_user(
                email=f'client{i+1}@example.com',
                password='testpass123',
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type='CLIENT',
                is_verified=random.choice([True, False])
            )
            users.append(user)
            self.stdout.write(f'Created client user: {user.email} (password: testpass123)')
        
        return users
    
    def create_test_files(self, users, count):
        self.stdout.write(f'Creating {count} test files...')
        files = []
        
        # Get operations users (only they can upload files)
        operations_users = [u for u in users if u.user_type == 'OPERATIONS']
        
        if not operations_users:
            self.stdout.write(self.style.WARNING('No operations users found to upload files'))
            return files
        
        # Create a test directory if it doesn't exist
        test_files_dir = os.path.join(settings.BASE_DIR, 'test_files')
        os.makedirs(test_files_dir, exist_ok=True)
        
        # Create sample files of different types
        file_types = ['DOCX', 'XLSX', 'PPTX']
        extensions = {
            'DOCX': '.docx',
            'XLSX': '.xlsx',
            'PPTX': '.pptx'
        }
        
        for i in range(count):
            # Create a sample file
            file_type = random.choice(file_types)
            filename = f'test_file_{i+1}{extensions[file_type]}'
            filepath = os.path.join(test_files_dir, filename)
            
            # Create a dummy file with some content
            with open(filepath, 'w') as f:
                f.write(f'This is a test {file_type} file. ' * 100)
            
            # Create file record in database
            with open(filepath, 'rb') as f:
                file_obj = File(
                    uploader=random.choice(operations_users),
                    file_type=file_type,
                    original_filename=filename,
                    description=fake.sentence(),
                )
                file_obj.file.save(filename, f, save=True)
                files.append(file_obj)
            
            self.stdout.write(f'Created test file: {file_obj.original_filename}')
        
        return files
    
    def create_test_share_links(self, users, files, count):
        self.stdout.write(f'Creating {count} test share links...')
        
        if not files:
            self.stdout.write(self.style.WARNING('No files available to create share links'))
            return
        
        for _ in range(count):
            file = random.choice(files)
            creator = random.choice(users)
            expires_in_days = random.randint(1, 30)
            
            share_link = FileShareLink.objects.create(
                file=file,
                created_by=creator,
                expires_at=datetime.now() + timedelta(days=expires_in_days),
                max_downloads=random.choice([None, 1, 5, 10]),
                is_active=random.choice([True, False])
            )
            
            self.stdout.write(
                f'Created share link for {file.original_filename} '
                f'(expires in {expires_in_days} days, active: {share_link.is_active})'
            )
