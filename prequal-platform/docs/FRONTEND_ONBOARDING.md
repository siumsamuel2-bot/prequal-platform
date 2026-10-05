# Frontend Engineer Onboarding Guide

Welcome to the Prequal engineering team! This guide will help you get up to speed with our frontend codebase quickly.

## Tech Stack

- **Framework**: React 18 with TypeScript
- **Routing**: React Router v6
- **Build Tool**: Vite
- **Charts**: Recharts
- **Testing**: Jest + Testing Library
- **Styling**: CSS (component-scoped files)

## Project Structure

```
prequal-platform/src/
├── api/
│   └── client.ts        # API client with typed endpoints
├── components/
│   ├── *.tsx            # React components
│   └── *.css            # Component-specific styles
├── hooks/
│   └── useAnalytics.ts # Analytics hook
├── styles/
│   ├── index.css        # Global styles
│   └── dashboard.css   # Shared component styles
├── utils/
│   └── auth.ts          # Authentication utilities
├── __tests__/           # Test files
└── __mocks__/           # Test mocks
```

## Key Patterns

### Component Structure

```tsx
import { useState, useEffect } from 'react';
import { SomeAPI } from '../api/client';
import { useToast } from './ToastContext';
import './ComponentName.css';

const ComponentName = () => {
  const toast = useToast();
  const [data, setData] = useState<Type | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await SomeAPI.getData();
        setData(result);
      } catch (err) {
        toast.error(err instanceof Error ? err.message : 'Failed to load');
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [toast]);

  if (loading) return <Loading message="Loading..." />;

  return (
    <div className="component-name">
      {/* content */}
    </div>
  );
};

export default ComponentName;
```

### API Calls

All API endpoints are defined in `src/api/client.ts`. Use the typed API functions:

```tsx
import { subcontractorApi, complianceApi } from '../api/client';

// GET request
const subcontractors = await subcontractorApi.getAll();

// POST request
const newSub = await subcontractorApi.create({ company_name: 'Acme', email: 'test@acme.com' });

// File upload
const formData = new FormData();
formData.append('file', file);
formData.append('certification_type', type);
const response = await fetch(`/api/subcontractors/${id}/credentials/upload`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
  body: formData,
});
```

### Authentication

Use the `isAuthenticated()` utility and `access_token` in localStorage:

```tsx
import { isAuthenticated } from '../utils/auth';

// Check auth in private routes
if (!isAuthenticated()) {
  return <Navigate to="/login" replace />;
}
```

### Toast Notifications

Use the ToastContext for user feedback:

```tsx
import { useToast } from './ToastContext';

const MyComponent = () => {
  const toast = useToast();
  
  const handleSave = async () => {
    try {
      await saveData();
      toast.success('Saved successfully');
    } catch (err) {
      toast.error('Failed to save');
    }
  };
};
```

### Routing

Routes are defined in `App.tsx` using React Router v6:

```tsx
<Route path="/subcontractors/:id" element={<SubcontractorProfile />} />
```

Access route params:

```tsx
import { useParams } from 'react-router-dom';

const { id } = useParams<{ id: string }>();
```

### Charts (Recharts)

```tsx
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

<ResponsiveContainer width="100%" height={300}>
  <LineChart data={chartData}>
    <CartesianGrid strokeDasharray="3 3" />
    <XAxis dataKey="date" />
    <YAxis />
    <Tooltip />
    <Line type="monotone" dataKey="value" stroke="#3b82f6" />
  </LineChart>
</ResponsiveContainer>
```

## CSS Conventions

- Component styles in `ComponentName.css` files
- BEM-like naming: `.component-name`, `.component-name__element`, `.component-name--modifier`
- CSS variables for colors defined in `src/styles/index.css`

## Development Workflow

### 1. Start Development Server

```bash
cd prequal-platform
npm run dev
```

### 2. Run Tests

```bash
npm test                    # Run all tests
npm test -- --watch        # Watch mode
npm test -- --coverage     # With coverage
```

### 3. Lint and Typecheck

```bash
npm run lint        # ESLint
npm run typecheck   # TypeScript
```

### 4. Build for Production

```bash
npm run build
```

## Common Tasks

### Adding a New API Endpoint

1. Open `src/api/client.ts`
2. Add your endpoint function following the existing pattern:

```typescript
export const myEntityApi = {
  getAll: () => apiClient.get<MyEntity[]>('/my-entities'),
  getById: (id: string) => apiClient.get<MyEntity>(`/my-entities/${id}`),
  create: (data: Omit<MyEntity, 'id'>) => apiClient.post<MyEntity>('/my-entities', data),
  update: (id: string, data: Partial<MyEntity>) => apiClient.put<MyEntity>(`/my-entities/${id}`, data),
  delete: (id: string) => apiClient.delete<{ message: string }>(`/my-entities/${id}`),
};
```

### Adding a New Route

1. Open `src/App.tsx`
2. Add the route inside the appropriate Routes block:

```tsx
<Route path="/my-new-page" element={<MyNewPage />} />
```

### Creating a New Component

1. Create `src/components/MyComponent.tsx`:

```tsx
import { useState } from 'react';
import { useToast } from './ToastContext';
import './MyComponent.css';

interface MyComponentProps {
  title: string;
  onSave?: (data: DataType) => void;
}

const MyComponent = ({ title, onSave }: MyComponentProps) => {
  const toast = useToast();
  // ... component logic
};

export default MyComponent;
```

2. Create `src/components/MyComponent.css`
3. Import and use in parent component

## Environment Variables

- `VITE_API_URL`: Backend API URL (defaults to `/api`)

## Useful Commands

```bash
npm run dev          # Start dev server
npm run build        # Production build
npm run preview      # Preview production build
npm test             # Run tests
npm run lint         # Lint code
npm run typecheck    # TypeScript check
```

## Getting Help

- See `docs/ONBOARDING.md` for customer onboarding flow (feature context)
- See `docs/ui-components.md` for UI component specifications
- Check `src/api/client.ts` for API endpoints
- Tag @CTO for technical questions