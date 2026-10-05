# Customer Onboarding Guide

Welcome to Prequal! This guide will walk you through the onboarding process to get your organization up and running with subcontractor compliance management.

## Onboarding Flow

The Prequal onboarding process consists of 3 steps:

### Step 1: Create Your Organization

After registering, you'll be redirected to `/setup` to create your organization.

- Enter your **Organization Name** (e.g., "Acme Construction")
- A URL **slug** is automatically generated
- Click **Create Organization**

You'll receive a confirmation email once your organization is set up.

### Step 2: Create Your First Project

A project represents a construction job site where you track subcontractor compliance.

1. Navigate to **Projects** in the sidebar
2. Click **New Project**
3. Fill in project details:
   - Project name and number
   - Client information
   - Project location
   - Start and end dates

### Step 3: Add Subcontractors

You can add subcontractors in two ways:

#### CSV Import (Recommended for bulk)

1. Navigate to **Subcontractors**
2. Click **Import Subcontractors**
3. Choose **CSV Upload**
4. Download the sample CSV template
5. Fill in your subcontractor data
6. Upload the file and review the import preview
7. Click **Import**

**Required CSV columns:** `company_name`, `email`

**Optional CSV columns:** `contact_first_name`, `contact_last_name`, `phone`, `address_line1`, `city`, `state`, `zip_code`, `license_number`, `license_state`, `ein`

#### Manual Entry

1. Navigate to **Subcontractors**
2. Click **Import Subcontractors**
3. Choose **Manual Entry**
4. Fill in the subcontractor details
5. Click **Add Subcontractor**

## Key Features

### Compliance Dashboard

The dashboard provides a real-time overview of your subcontractor compliance status:

- **Total/Active Subcontractors**: Count of all and active subcontractors
- **Compliance Rate**: Percentage of compliant subcontractors
- **Expiring This Month**: Certifications expiring within 30 days
- **Open Violations**: Unresolved safety or regulatory violations

### Certification Tracking

- Upload and track subcontractor certifications (OSHA, contractor licenses, insurance, etc.)
- Set expiration alerts to avoid lapsed coverage
- Verification status tracking

### Alert System

Prequal automatically monitors and alerts you to:

- Expiring certifications (30, 14, and 7 days before expiration)
- New violations
- Compliance status changes

Alerts appear in the dashboard and are sent via email.

### First-Run Tutorial

When you first log in, a checklist on the dashboard guides you through the initial setup:

1. Set up organization
2. Create first project
3. Add subcontractors

The checklist disappears once all steps are completed.

## Next Steps

- Explore the **Compliance Dashboard** for real-time insights
- Set up **Email Notifications** in Settings to receive alerts
- Review **API Documentation** at `/api/docs` for integration options
- Add team members in **Settings > Team**

## Support

For questions or assistance:
- Email: support@prequal.example.com
- Documentation: See other docs in this folder
- API: See API documentation at `/api/docs`