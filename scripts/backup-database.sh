#!/bin/bash
# Database Backup Automation Script
# This script creates automated backups of the RDS PostgreSQL database
# and stores them in S3 with lifecycle policies for retention management.

set -euo pipefail

# Configuration
AWS_REGION="${AWS_REGION:-us-east-1}"
DB_IDENTIFIER="${DB_IDENTIFIER:-prequal-db}"
BACKUP_BUCKET="${BACKUP_BUCKET:-prequal-db-backups}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="prequal-db-backup-${TIMESTAMP}"

# Logging
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

error() {
    log "ERROR: $1"
    exit 1
}

# Create RDS snapshot
create_rds_snapshot() {
    log "Creating RDS snapshot: ${BACKUP_NAME}"
    
    aws rds create-db-snapshot \
        --db-instance-identifier "${DB_IDENTIFIER}" \
        --db-snapshot-identifier "${BACKUP_NAME}" \
        --region "${AWS_REGION}"
    
    log "Waiting for snapshot creation to complete..."
    
    aws rds wait db-snapshot-completed \
        --db-snapshot-identifier "${BACKUP_NAME}" \
        --region "${AWS_REGION}"
    
    log "Snapshot created successfully: ${BACKUP_NAME}"
}

# Export snapshot to S3 (optional, for long-term storage)
export_snapshot_to_s3() {
    log "Exporting snapshot to S3: s3://${BACKUP_BUCKET}/${BACKUP_NAME}"
    
    aws rds export-snapshot-to-s3 \
        --export-identifier "${BACKUP_NAME}-export" \
        --source-type "SNAPSHOT" \
        --source-identifier "${BACKUP_NAME}" \
        --s3-bucket-name "${BACKUP_BUCKET}" \
        --s3-prefix "exports/${BACKUP_NAME}" \
        --region "${AWS_REGION}"
    
    log "Export initiated. Check AWS Console for completion."
}

# Create logical backup using pg_dump (requires database access)
create_logical_backup() {
    log "Creating logical backup using pg_dump"
    
    # Get RDS endpoint
    DB_ENDPOINT=$(aws rds describe-db-instances \
        --db-instance-identifier "${DB_IDENTIFIER}" \
        --query 'DBInstances[0].Endpoint.Address' \
        --output text \
        --region "${AWS_REGION}")
    
    DB_PORT=$(aws rds describe-db-instances \
        --db-instance-identifier "${DB_IDENTIFIER}" \
        --query 'DBInstances[0].Endpoint.Port' \
        --output text \
        --region "${AWS_REGION}")
    
    # Get database name from environment or default
    DB_NAME="${DB_NAME:-prequal_prod}"
    
    # Create backup
    PGPASSWORD="${DB_PASSWORD}" pg_dump \
        -h "${DB_ENDPOINT}" \
        -p "${DB_PORT}" \
        -U postgres \
        -d "${DB_NAME}" \
        -F c \
        -b \
        -v \
        --file="/tmp/${BACKUP_NAME}.dump"
    
    # Upload to S3
    aws s3 cp "/tmp/${BACKUP_NAME}.dump" "s3://${BACKUP_BUCKET}/logical/${BACKUP_NAME}.dump"
    
    # Cleanup local file
    rm -f "/tmp/${BACKUP_NAME}.dump"
    
    log "Logical backup uploaded to S3: s3://${BACKUP_BUCKET}/logical/${BACKUP_NAME}.dump"
}

# Cleanup old snapshots
cleanup_old_snapshots() {
    log "Cleaning up snapshots older than ${RETENTION_DAYS} days"
    
    CUTOFF_DATE=$(date -d "-${RETENTION_DAYS} days" +%Y-%m-%dT%H:%M:%S)
    
    # Get list of old snapshots
    OLD_SNAPSHOTS=$(aws rds describe-db-snapshots \
        --db-instance-id "${DB_IDENTIFIER}" \
        --query "DBSnapshots[?SnapshotCreateTime<='${CUTOFF_DATE}' && SnapshotStatus=='available'].DBSnapshotIdentifier" \
        --output text \
        --region "${AWS_REGION}")
    
    # Delete old snapshots
    for SNAPSHOT in ${OLD_SNAPSHOTS}; do
        if [[ "${SNAPSHOT}" == prequal-db-backup-* ]]; then
            log "Deleting old snapshot: ${SNAPSHOT}"
            aws rds delete-db-snapshot \
                --db-snapshot-identifier "${SNAPSHOT}" \
                --region "${AWS_REGION}"
        fi
    done
    
    log "Cleanup completed"
}

# Verify backup
verify_backup() {
    log "Verifying backup: ${BACKUP_NAME}"
    
    STATUS=$(aws rds describe-db-snapshots \
        --db-snapshot-identifier "${BACKUP_NAME}" \
        --query 'DBSnapshots[0].Status' \
        --output text \
        --region "${AWS_REGION}")
    
    if [[ "${STATUS}" == "available" ]]; then
        log "Backup verification successful: ${BACKUP_NAME} is available"
        return 0
    else
        log "Backup verification failed: ${BACKUP_NAME} status is ${STATUS}"
        return 1
    fi
}

# Send notification
send_notification() {
    local STATUS="$1"
    local MESSAGE="$2"
    
    log "Sending notification: ${STATUS} - ${MESSAGE}"
    
    # SNS notification (if configured)
    if [[ -n "${SNS_TOPIC_ARN:-}" ]]; then
        aws sns publish \
            --topic-arn "${SNS_TOPIC_ARN}" \
            --subject "Database Backup ${STATUS}" \
            --message "${MESSAGE}" \
            --region "${AWS_REGION}"
    fi
    
    # Slack notification (if webhook configured)
    if [[ -n "${SLACK_WEBHOOK_URL:-}" ]]; then
        curl -X POST "${SLACK_WEBHOOK_URL}" \
            -H 'Content-Type: application/json' \
            -d "{
                \"text\": \"Database Backup ${STATUS}\",
                \"blocks\": [
                    {
                        \"type\": \"section\",
                        \"text\": {
                            \"type\": \"mrkdwn\",
                            \"text\": \"*Database Backup ${STATUS}*\\n${MESSAGE}\"
                        }
                    }
                ]
            }"
    fi
}

# Main execution
main() {
    log "Starting database backup process"
    log "Database: ${DB_IDENTIFIER}"
    log "Region: ${AWS_REGION}"
    log "Retention: ${RETENTION_DAYS} days"
    
    # Create snapshot
    create_rds_snapshot
    
    # Verify backup
    if verify_backup; then
        send_notification "SUCCESS" "Backup completed: ${BACKUP_NAME}"
    else
        send_notification "FAILURE" "Backup verification failed: ${BACKUP_NAME}"
        error "Backup verification failed"
    fi
    
    # Export to S3 (optional)
    if [[ "${EXPORT_TO_S3:-false}" == "true" ]]; then
        export_snapshot_to_s3
    fi
    
    # Create logical backup (optional)
    if [[ "${LOGICAL_BACKUP:-false}" == "true" ]]; then
        create_logical_backup
    fi
    
    # Cleanup old backups
    cleanup_old_snapshots
    
    log "Backup process completed successfully"
}

# Run main function
main "$@"
