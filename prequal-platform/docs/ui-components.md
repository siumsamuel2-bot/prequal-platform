# Frontend Wireframes and Dashboard UI Documentation

## Component Overview

### Dashboard.jsx
- Main dashboard component that orchestrates all other components
- Uses React Router for navigation
- Imports and renders SubcontractorProfile, CertificationAlerts, and CredentialUpload components

### SubcontractorProfile.jsx
- Form component for viewing/editing subcontractor information
- Includes fields for company name, contact person, email, phone, and address
- Designed for both viewing existing data and adding new subcontractors

### CertificationAlerts.jsx
- Alert system for certification expiration tracking
- Displays critical and warning level alerts
- Color-coded status indicators for quick visual reference

### CredentialUpload.jsx
- File upload portal for subcontractor credentials
- Supports multiple file selection
- Document type selection dropdown

## Design System

### Color Palette
- Primary: #0275d8 (Bootstrap blue)
- Critical Alert: #d9534f (Bootstrap red)
- Warning Alert: #f0ad4e (Bootstrap orange)
- Background: #f8f9fa (Light gray)
- Text: #333 (Dark gray)

### Typography
- Font: Arial, sans-serif
- Headings: 24px, 20px, 18px
- Body: 16px

### Spacing
- Padding: 20px (container), 10px (elements)
- Margins: 30px (sections), 15px (elements)

## Implementation Notes

- All components are built with React functional components
- CSS classes follow BEM methodology
- Responsive design using flexbox
- Accessible form elements with proper labeling