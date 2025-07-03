# Secure File Sharing System

A secure file sharing system built with Django and Django REST Framework that allows operations users to upload files and client users to download them securely.

## Features

- User authentication (JWT-based)
- Two types of users: Operations and Client
- File upload (limited to .pptx, .docx, .xlsx for ops users)
- Secure file download with expiring, encrypted URLs
- Email verification for client users
- RESTful API endpoints

## Tech Stack

- **Backend**: Django 4.2, Django REST Framework
- **Database**: PostgreSQL
- **Task Queue**: Celery with Redis
- **File Storage**: MinIO (S3-compatible)
- **Authentication**: JWT
- **Documentation**: Swagger/OpenAPI

## Setup

1. Clone the repository
2. Create and activate a virtual environment
3. Install requirements: `pip install -r requirements/dev.txt`
4. Set up environment variables (copy `.env.example` to `.env` and configure)
5. Run migrations: `python manage.py migrate`
6. Start the development server: `python manage.py runserver`

## API Documentation

API documentation is available at `/api/docs/` when the development server is running.

## Running Tests

```bash
pytest
```
