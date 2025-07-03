#!/bin/bash

# Configuration
BACKUP_DIR="/backups/securefiles"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/backup_${TIMESTAMP}.sql"
MEDIA_BACKUP="${BACKUP_DIR}/media_${TIMESTAMP}.tar.gz"
KEEP_DAYS=30

# Load environment variables
if [ -f "/opt/secure-file-system/.env" ]; then
    export $(grep -v '^#' /opt/secure-file-system/.env | xargs)
fi

# Create backup directory if it doesn't exist
mkdir -p "${BACKUP_DIR}"

# Database backup
echo "Creating database backup..."
PGPASSWORD="${DB_PASSWORD}" pg_dump -h "${DB_HOST}" -U "${DB_USER}" -F c -b -v -f "${BACKUP_FILE}" "${DB_NAME}"

if [ $? -eq 0 ]; then
    echo "Database backup created: ${BACKUP_FILE}"
else
    echo "Error creating database backup!"
    exit 1
fi

# Media files backup
echo "Creating media files backup..."
tar -czf "${MEDIA_BACKUP}" -C "$(dirname "${MEDIA_ROOT:-/opt/secure-file-system/media}")" "$(basename "${MEDIA_ROOT:-/opt/secure-file-system/media}")"

if [ $? -eq 0 ]; then
    echo "Media backup created: ${MEDIA_BACKUP}"
else
    echo "Error creating media backup!"
    exit 1
fi

# Clean up old backups
echo "Cleaning up backups older than ${KEEP_DAYS} days..."
find "${BACKUP_DIR}" -type f -name "backup_*.sql" -mtime +${KEEP_DAYS} -delete
find "${BACKUP_DIR}" -type f -name "media_*.tar.gz" -mtime +${KEEP_DAYS} -delete

echo "Backup completed successfully!"

# Optional: Sync to remote storage (uncomment and configure as needed)
# echo "Syncing to remote storage..."
# rclone sync "${BACKUP_DIR}" "your-remote:securefiles-backups" --delete-excluded

exit 0
