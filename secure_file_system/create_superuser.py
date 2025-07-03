import os
import django

def main():
    # Set up Django environment
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    django.setup()
    
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    
    # Create superuser if it doesn't exist
    if not User.objects.filter(email='admin@example.com').exists():
        User.objects.create_superuser(
            email='admin@example.com',
            password='admin123',
            user_type='OPERATIONS',
            is_active=True,
            is_staff=True,
            is_superuser=True
        )
        print("Superuser created successfully!")
    else:
        print("Superuser already exists!")

if __name__ == "__main__":
    main()
