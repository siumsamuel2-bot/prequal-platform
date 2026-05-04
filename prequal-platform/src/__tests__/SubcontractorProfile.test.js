import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import SubcontractorProfile from '../components/SubcontractorProfile';

describe('SubcontractorProfile', () => {
  test('renders subcontractor profile with all sections', () => {
    render(<SubcontractorProfile />);
    
    expect(screen.getByText('SUBCONTRACTOR COMPLIANCE PROFILE')).toBeInTheDocument();
  });
});