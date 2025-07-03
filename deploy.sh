#!/bin/bash

# Exit on any error
set -e

echo "Starting deployment..."

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "Creating .env file from .env.example..."
    cp .env.example .env
    echo "Please edit the .env file with your configuration and run this script again."
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

echo "Building and starting Docker containers..."
docker-compose up -d --build

echo "Waiting for PostgreSQL to be ready..."
until docker-compose exec db pg_isready -U $DB_USER -d $DB_NAME; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo "Running database migrations..."
docker-compose exec web python manage.py migrate --noinput

echo "Collecting static files..."
docker-compose exec web python manage.py collectstatic --noinput

echo "Creating superuser if not exists..."
docker-compose exec web python manage.py createsuperuser --noinput --email admin@example.com --username admin 2>/dev/null || true

echo "Deployment completed successfully!"
echo "Application is running at http://localhost:8000"
echo "Admin interface: http://localhost:8000/admin"
echo "API Documentation: http://localhost:8000/api/docs/"

echo "To view logs, run: docker-compose logs -f"
