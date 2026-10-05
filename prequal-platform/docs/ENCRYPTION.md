# Data Encryption at Rest - Prequal Platform

## Overview

This document describes the encryption at rest implementation for the Prequal subcontractor compliance platform. All sensitive PII and customer data is encrypted at the column level before storage.

## Encryption Architecture

### Two-Layer Encryption

1. **Application-Layer Encryption (Column-Level)**: Sensitive fields are encrypted before storage using Fernet symmetric encryption or AWS KMS.
2. **Database-Level Encryption (TDE)**: AWS RDS storage encryption is enabled with KMS key management.

### Fields Encrypted

#### Subcontractors Table (`subcontractors`)
| Field | Encrypted Column | Notes |
|-------|-----------------|-------|
| contact_first_name | encrypted_contact_first_name | |
| contact_last_name | encrypted_contact_last_name | |
| email | encrypted_email | |
| phone | encrypted_phone | |
| address_line1 | encrypted_address_line1 | |
| address_line2 | encrypted_address_line2 | |
| city | encrypted_city | |
| state | encrypted_state | |
| zip_code | encrypted_zip_code | |
| ein | encrypted_ein | EIN is highly sensitive |

#### Projects Table (`projects`)
| Field | Encrypted Column | Notes |
|-------|-----------------|-------|
| client_name | encrypted_client_name | Customer contact name |
| client_contact | encrypted_client_contact | Customer contact info |

## Implementation Details

### Encryption Service

Location: `app/services/encryption_service.py`

#### Key Management

- **Development**: Uses `SECRET_KEY` or `ENCRYPTION_KEY` environment variable
- **Production**: Uses AWS KMS via `AWS_KMS_KEY_ID` and `AWS_REGION` environment variables

#### Key Derivation

For keys shorter than 32 characters, PBKDF2HMAC is used with:
- Algorithm: SHA256
- Salt: `prequal_salt` (static, not a security issue for key derivation)
- Iterations: 480,000

### Encryption Flow

1. **On Write (Create/Update)**:
   - PII fields are encrypted using `encrypt_value()`
   - Encrypted values stored in `encrypted_*` columns
   - Plaintext columns are set to NULL

2. **On Read**:
   - Encrypted columns are decrypted using `decrypt_value()`
   - Decrypted values are populated in plaintext columns for API response
   - All PII access is logged via `log_data_access()`

### API Integration

The compliance router (`app/routers/compliance.py`) handles encryption transparently:

```python
# Create - encrypts before saving
db_subcontractor = Subcontractor(**subcontractor.model_dump())
_encrypt_pii_fields(db_subcontractor, subcontractor.model_dump())

# Read - decrypts for response
for field in PII_FIELDS + ["ein", "email"]:
    val = decrypt_pii(subcontractor, field)
    if val:
        setattr(subcontractor, field, val)
```

## Database Migrations

Migrations handle backfilling existing data:

- `015_encrypt_subcontractor_ein.py`: Adds `encrypted_ein` column
- `016_encrypt_subcontractor_pii.py`: Adds encrypted PII columns for subcontractors
- `017_encrypt_client_data.py`: Adds encrypted columns for projects table

### Migration Process

1. Add new encrypted columns (nullable)
2. Backfill existing plaintext data
3. Set plaintext columns to NULL
4. Verification

## Key Rotation Procedure

### Application Keys (Non-KMS)

1. Generate new key
2. Update `ENCRYPTION_KEY` environment variable
3. Run migration to re-encrypt with new key
4. Verify all data is accessible

### AWS KMS Keys

KMS key rotation is enabled automatically (annual rotation per AWS policy).

To rotate manually:
```bash
aws kms rotate-key --key-id alias/prequal-rds-encryption
```

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `ENCRYPTION_KEY` | Application encryption key | Yes (dev) |
| `SECRET_KEY` | Fallback encryption key | No |
| `AWS_KMS_KEY_ID` | KMS key ID for production | Production |
| `AWS_REGION` | AWS region for KMS | Production |

## Security Considerations

1. **Key Storage**: Keys should never be committed to version control
2. **Key Separation**: Application keys differ from database encryption keys
3. **Audit Logging**: All PII access is logged
4. **Access Control**: Only application services have access to decryption keys

## Verification

To verify encryption is working:

1. Check database directly - encrypted columns should contain ciphertext
2. Run API and verify decrypted data is returned correctly
3. Check audit logs for data access entries

## Rollback

If rollback is needed, migrations include `downgrade()` functions that:
1. Decrypt all values
2. Restore plaintext columns
3. Drop encrypted columns

**Warning**: Downgrade should only be used in emergencies as it exposes plaintext data.