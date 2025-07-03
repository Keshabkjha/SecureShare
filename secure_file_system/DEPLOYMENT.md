# Secure File System - Deployment Guide

This guide will walk you through deploying the Secure File System application to a production environment.

## Prerequisites

- Ubuntu 20.04/22.04 server
- Python 3.8+
- PostgreSQL
- Redis
- Nginx
- Domain name (recommended)

## 1. Server Setup

### 1.1 Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

### 1.2 Install Required System Packages

```bash
sudo apt install -y python3-pip python3-dev libpq-dev postgresql postgresql-contrib nginx redis-server
```

### 1.3 Create a System User

```bash
sudo adduser --system --group --no-create-home securefiles
```

## 2. Database Setup

### 2.1 Create PostgreSQL Database and User

```bash
sudo -u postgres psql
```

In PostgreSQL prompt:

```sql
CREATE DATABASE securefiles_db;
CREATE USER securefiles_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE securefiles_db TO securefiles_user;
\q
```

## 3. Application Setup

### 3.1 Clone the Repository

```bash
cd /opt
sudo git clone https://github.com/yourusername/secure-file-system.git
sudo chown -R securefiles:securefiles /opt/secure-file-system
```

### 3.2 Set Up Python Environment

```bash
cd /opt/secure-file-system
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3.3 Configure Environment Variables

Create a `.env` file:

```bash
cp .env.example .env
nano .env
```

Update with your production settings:

```env
DEBUG=False
SECRET_KEY=your-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# Database
DB_NAME=securefiles_db
DB_USER=securefiles_user
DB_PASSWORD=your_secure_password
DB_HOST=localhost
DB_PORT=5432

# Email (example for Gmail)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=your-email@example.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Application URL
BASE_URL=https://yourdomain.com
```

### 3.4 Run Migrations

```bash
python manage.py migrate
python manage.py collectstatic --noinput
```

### 3.5 Create Superuser

```bash
python manage.py createsuperuser
```

## 4. Configure Gunicorn

### 4.1 Create Gunicorn Service

```bash
sudo nano /etc/systemd/system/securefiles.service
```

Add:

```ini
[Unit]
Description=Secure Files Gunicorn Service
After=network.target

[Service]
User=securefiles
Group=www-data
WorkingDirectory=/opt/secure-file-system
Environment="PATH=/opt/secure-file-system/venv/bin"
ExecStart=/opt/secure-file-system/venv/bin/gunicorn \
    --access-logfile - \
    --workers 3 \
    --bind unix:/run/securefiles.sock \
    config.wsgi:application

[Install]
WantedBy=multi-user.target
```

### 4.2 Start Gunicorn

```bash
sudo systemctl start securefiles
sudo systemctl enable securefiles
```

## 5. Configure Nginx

### 5.1 Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/securefiles
```

Add:

```nginx
upstream securefiles_server {
    server unix:/run/securefiles.sock fail_timeout=0;
}

server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com www.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;
    
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_ciphers 'EECDH+AESGCM:EDH+AESGCM:AES256+EECDH:AES256+EDH';
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 10m;

    client_max_body_size 100M;

    location /static/ {
        alias /opt/secure-file-system/staticfiles/;
        expires 30d;
    }

    location /media/ {
        alias /opt/secure-file-system/media/;
        expires 30d;
    }

    location /api/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_pass http://securefiles_server;
    }

    location /admin/ {
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Host $http_host;
        proxy_redirect off;
        proxy_pass http://securefiles_server;
    }

    location / {
        root /var/www/securefiles/frontend;
        try_files $uri $uri/ /index.html;
    }
}
```

### 5.2 Enable the Site

```bash
sudo ln -s /etc/nginx/sites-available/securefiles /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

## 6. Set Up SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

## 7. Configure Celery

### 7.1 Create Celery Service

```bash
sudo nano /etc/systemd/system/celery.service
```

Add:

```ini
[Unit]
Description=Celery Service
After=network.target

[Service]
Type=simple
User=securefiles
Group=securefiles
EnvironmentFile=/opt/secure-file-system/.env
WorkingDirectory=/opt/secure-file-system
ExecStart=/opt/secure-file-system/venv/bin/celery -A config worker --loglevel=info
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 7.2 Start Celery

```bash
sudo systemctl start celery
sudo systemctl enable celery
```

## 8. Set Up Logging

```bash
sudo mkdir -p /var/log/securefiles/
sudo chown -R securefiles:securefiles /var/log/securefiles/
```

## 9. Final Steps

1. Set proper permissions:
   ```bash
   sudo chown -R securefiles:www-data /opt/secure-file-system
   sudo chmod -R 755 /opt/secure-file-system
   ```

2. Restart all services:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl restart securefiles
   sudo systemctl restart nginx
   sudo systemctl restart celery
   ```

## 10. Verify Installation

1. Visit `https://yourdomain.com/admin` and log in
2. Test API endpoints
3. Check logs for any errors:
   ```bash
   sudo journalctl -u securefiles
   sudo journalctl -u celery
   sudo tail -f /var/log/nginx/error.log
   ```

## 11. Backup Strategy

Set up regular backups for your database and media files:

```bash
# Example backup script
#!/bin/bash

# Database backup
PGPASSWORD=your_db_password pg_dump -U securefiles_user -h localhost securefiles_db > /backups/securefiles_db_$(date +%Y%m%d).sql

# Media files backup
tar -czf /backups/securefiles_media_$(date +%Y%m%d).tar.gz /opt/secure-file-system/media/

# Rotate backups (keep last 30 days)
find /backups/ -type f -mtime +30 -delete
```

Schedule with cron:

```
0 2 * * * /path/to/backup_script.sh
```

## 12. Security Considerations

1. Keep system and dependencies updated
2. Use strong passwords
3. Implement rate limiting
4. Set up monitoring
5. Regular security audits
6. Keep backups in a secure location

## 13. Scaling (Optional)

For higher traffic:
1. Add more Gunicorn workers
2. Set up database replication
3. Use a CDN for static/media files
4. Implement caching with Redis
5. Consider containerization with Docker

## Support

For issues, please open an issue on the GitHub repository.
