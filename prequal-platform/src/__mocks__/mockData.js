// Mock data for testing
export const mockSubcontractorData = {
  id: 1,
  companyName: 'ABC Construction',
  contactPerson: 'John Smith',
  contactEmail: 'john@abcconstruction.com',
  phone: '555-123-4567',
  address: '123 Construction Ave, Building City, BC 12345'
};

export const mockCertificationAlerts = [
  {
    id: 1,
    type: 'critical',
    message: 'Certification expiring in 30 days',
    subcontractorId: 1
  },
  {
    id: 2,
    type: 'warning',
    message: 'Documentation requires verification',
    subcontractorId: 2
  }
];

export const mockDocumentTypes = [
  'Insurance Certificate',
  'License',
  'OSHA Training Certificate'
];