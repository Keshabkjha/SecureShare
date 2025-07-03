# Secure File Sharing System

A secure file sharing system built with Django REST Framework, featuring role-based access control, secure file downloads, and email notifications.

## Features

- User authentication with JWT
- Role-based access control (Operations and Client users)
- Secure file upload and download with expiring tokens
- File sharing with expiring links
- Email notifications for file uploads
- API documentation with Swagger UI
- Containerized with Docker
- Background tasks with Celery and Redis
- PostgreSQL database

## Prerequisites

- Docker and Docker Compose
- Python 3.9+
- Node.js and npm (for frontend development, if needed)

## Getting Started

### 1. Clone the repository

```bash
git clone <repository-url>
cd secure-file-system
```

### 2. Set up environment variables

Copy the example environment files and update them with your configuration:

```bash
cp .env.example .env
cp .env.db.example .env.db
```

Edit the `.env` file with your settings:

```bash
# Django Settings
DEBUG=True
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_NAME=securefiles
DB_USER=postgres
DB_PASSWORD=postgres
DB_HOST=db
DB_PORT=5432

# Email Settings
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend  # Use console backend for development
DEFAULT_FROM_EMAIL=noreply@example.com

# Frontend URL (for email links)
FRONTEND_URL=http://localhost:3000
```

### 3. Start the application

Use the deployment script to start all services:

```bash
chmod +x deploy.sh
./deploy.sh
```

Or start services manually:

```bash
docker-compose up -d --build
```

### 4. Run database migrations

```bash
docker-compose exec web python manage.py migrate
```

### 5. Create a superuser (admin)

```bash
docker-compose exec web python manage.py createsuperuser
```

### 6. Access the application

- API: http://localhost:8000/api/
- Admin: http://localhost:8000/admin/
- API Documentation: http://localhost:8000/api/docs/

## API Endpoints

### Authentication

- `POST /api/v1/auth/register/` - Register a new user
- `POST /api/v1/auth/login/` - Login and get JWT tokens
- `POST /api/v1/auth/refresh/` - Refresh access token
- `POST /api/v1/auth/verify-email/` - Verify email address

### Files

- `GET /api/v1/files/` - List all files (filtered by user role)
- `POST /api/v1/files/upload/` - Upload a new file (Ops only)
- `GET /api/v1/files/{id}/` - Get file details
- `GET /api/v1/files/{id}/download/` - Get secure download URL
- `DELETE /api/v1/files/{id}/` - Delete a file

### File Sharing

- `POST /api/v1/files/shares/` - Create a shareable link
- `GET /api/v1/files/shares/{token}/` - Download file using share token

## Development

### Running Tests

```bash
docker-compose exec web python manage.py test
```

### Linting and Code Style

```bash
# Run black
black .

# Run flake8
flake8

# Run isort
isort .
```

### API Documentation

The API documentation is available at `/api/docs/` when running the development server.

## Production Deployment

For production deployment, make sure to:

1. Set `DEBUG=False` in `.env`
2. Configure a real email backend in `.env`
3. Set appropriate security headers
4. Use HTTPS with a valid certificate
5. Configure proper database backups

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with Django REST Framework
- Uses JWT for authentication
- Containerized with Docker
- Background tasks with Celery and Redis
