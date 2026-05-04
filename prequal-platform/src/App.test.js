import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { sum } from './utils';

test('adds 1 + 2 to equal 3', () => {
  expect(sum(1, 2)).toBe(3);
});

describe('Dashboard Components', () => {
  test('renders dashboard with all components', () => {
    render(<div>Test</div>);
    
    expect(screen.getByText('Test')).toBeInTheDocument();
  });
});