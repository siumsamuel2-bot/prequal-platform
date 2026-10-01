# UI Component Library — Prequal Platform

**Last Updated**: 2026-07-04
**Related Issues**: [MID-432](/MID/issues/MID-432)

---

## Overview

The `src/components/ui/` folder contains reusable, accessible, typed React components that form the foundation of the Prequal UI. These components are used throughout the application and should be the default choice over inline ad-hoc markup.

---

## Component Inventory

### Core Form Components

| Component | File | Description |
|-----------|------|-------------|
| `Button` | `ui/Button.tsx` | Primary action trigger. Variants: primary, secondary, danger, ghost. Sizes: sm, md, lg. Supports loading state, icons. |
| `Input` | `ui/Input.tsx` | Text input with label, error, hint, and icon support. |
| `Textarea` | `ui/Textarea.tsx` | Multi-line text input with label, error, hint support. |
| `Select` | `ui/Select.tsx` | Dropdown select with label, error, hint. |
| `Checkbox` | `ui/Checkbox.tsx` | Checkbox input with label. |

### Display Components

| Component | File | Description |
|-----------|------|-------------|
| `Badge` | `ui/Badge.tsx` | Status indicator label. Variants: default, success, warning, danger, info. |
| `Card` | `ui/Card.tsx` | Container with optional header, content, footer. |
| `Avatar` | `ui/Avatar.tsx` | User avatar with initials fallback. Supports AvatarGroup. |
| `Alert` | `ui/Alert.tsx` | Contextual feedback message. Variants: info, success, warning, error. |
| `Table` | `ui/Table.tsx` | Data table with sorting, pagination, row selection. |
| `Tooltip` | `ui/Tooltip.tsx` | Contextual information on hover/focus. |

### Overlay Components

| Component | File | Description |
|-----------|------|-------------|
| `Modal` | `ui/Modal.tsx` | Dialog overlay with focus trap. |

---

## Standards

### 1. TypeScript

All components must be written in TypeScript with explicit prop interfaces.

```typescript
type ButtonVariant = 'primary' | 'secondary' | 'danger' | 'ghost';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: 'sm' | 'md' | 'lg';
  loading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}
```

Use `React.FC` for the component function type. Prefer extending native HTML attribute interfaces when appropriate (e.g., `React.ButtonHTMLAttributes<HTMLButtonElement>`) to inherit all valid button attributes.

### 2. Styling

Components use **inline styles** via `React.CSSProperties`. This keeps components self-contained with no external CSS dependencies.

**Style constants** are defined as plain objects:

```typescript
const variantStyles: Record<ButtonVariant, React.CSSProperties> = {
  primary: { backgroundColor: '#3b82f6', color: '#ffffff', border: 'none' },
  secondary: { backgroundColor: '#ffffff', color: '#374151', border: '1px solid #d1d5db' },
  danger: { backgroundColor: '#ef4444', color: '#ffffff', border: 'none' },
  ghost: { backgroundColor: 'transparent', color: '#374151', border: 'none' },
};
```

**Spacing**: Use 4px base unit. Common values: 4, 8, 12, 16, 20, 24, 32, 48px.
**Border radius**: 4px (small), 6px (default), 8px (large), 9999px (pill).
**Color palette**: Use existing tokens — primary blue `#3b82f6`, danger red `#ef4444`, gray scale `#374151` (text), `#6b7280` (secondary text), `#e5e7eb` (borders).

### 3. Accessibility

Accessibility is **required**, not optional. Every component must pass these checks:

**Labels and IDs**
- All form inputs must have an associated `<label>` with correct `htmlFor`/`id` pairing.
- Use `useId()` or a deterministic ID pattern to generate unique IDs when not provided.

**Error messaging**
- Inputs with errors must set `aria-invalid="true"`.
- Error messages must be referenced via `aria-describedby` on the input.
- Error text should have `role="alert"` so screen readers announce it.

```tsx
<input
  id={inputId}
  aria-invalid={hasError}
  aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
/>
{error && (
  <span id={`${inputId}-error`} role="alert" style={{ fontSize: '12px', color: '#ef4444' }}>
    {error}
  </span>
)}
```

**Focus management**
- Modals and dialogs must trap focus within the component.
- Keyboard navigation (Tab, Escape, Arrow keys) must work correctly.
- Modal dialogs must have `role="dialog"`, `aria-modal="true"`, and `aria-labelledby` pointing to the title.

**Tooltips**
- Must be referenced via `aria-describedby` on the trigger element.
- Must be keyboard accessible (show on focus, not just hover).
- Must not trap keyboard focus.

**Color contrast**
- Text must meet WCAG AA contrast ratios (4.5:1 for body text, 3:1 for large text).
- Never convey information by color alone — pair with text or icons.

### 4. Component Composition

Prefer composition over configuration. Components should accept `React.ReactNode` for content slots:

```tsx
interface CardProps {
  children: React.ReactNode;
  title?: string;
  action?: React.ReactNode;
}
```

Avoid prop drilling. Use React context for widely shared state (e.g., `ToastContext`).

### 5. Null Safety

Components must not throw on null/undefined data. Use optional chaining and nullish coalescing:

```tsx
// Good
<span>{user?.name ?? 'Unknown'}</span>

// Bad — will crash on null user
<span>{user.name}</span>
```

### 6. Export Pattern

All UI components are exported from `src/components/ui/index.ts`. Add new components here:

```typescript
export { Button } from './Button';
export { Table, type TableColumn, type TableProps } from './Table';
```

---

## Usage Examples

### Button with loading state

```tsx
import { Button } from './ui';

<Button variant="primary" loading={isSubmitting} onClick={handleSubmit}>
  Save Changes
</Button>
```

### Input with validation error

```tsx
import { Input } from './ui';

<Input
  label="Email Address"
  type="email"
  value={email}
  onChange={(e) => setEmail(e.target.value)}
  error={errors.email}
  hint="We'll never share your email."
/>
```

### Data Table with sorting

```tsx
import { Table, Badge, type TableColumn } from './ui';

const columns: TableColumn<Subcontractor>[] = [
  {
    key: 'name',
    header: 'Company',
    sortable: true,
    render: (value) => <strong>{String(value)}</strong>,
  },
  {
    key: 'complianceStatus',
    header: 'Status',
    render: (value) => (
      <Badge variant={value === 'compliant' ? 'success' : 'danger'}>
        {String(value)}
      </Badge>
    ),
  },
];

<Table
  columns={columns}
  data={subcontractors}
  keyExtractor={(row) => row.id}
  onRowClick={(row) => navigate(`/subcontractors/${row.id}`)}
  sortState={sortState}
  onSort={(key, direction) => setSortState({ key, direction })}
  pagination={{
    page,
    pageSize: 20,
    total,
    onPageChange: setPage,
  }}
/>
```

### Tooltip wrapping a button

```tsx
import { Tooltip, Button } from './ui';

<Tooltip content="Delete this subcontractor" position="top">
  <Button variant="danger" size="sm" onClick={handleDelete}>
    Delete
  </Button>
</Tooltip>
```

---

## Creating a New Component

1. Create the file in `src/components/ui/` (e.g., `src/components/ui/Tag.tsx`).
2. Use `React.FC<PropsInterface>` with TypeScript.
3. Follow the inline style pattern — define style objects as constants.
4. Include full accessibility attributes (labels, ARIA, keyboard support).
5. Export from `src/components/ui/index.ts`.
6. Add entry to this document.

---

## Design Tokens (Reference)

| Token | Value | Usage |
|-------|-------|-------|
| Primary | `#3b82f6` | Primary buttons, links, active states |
| Primary Hover | `#2563eb` | Button hover state |
| Danger | `#ef4444` | Destructive actions, errors |
| Danger Hover | `#dc2626` | Danger button hover |
| Text Primary | `#374151` | Body text |
| Text Secondary | `#6b7280` | Descriptions, hints |
| Border | `#d1d5db` | Input borders, dividers |
| Background | `#ffffff` | Card backgrounds |
| Surface | `#f9fafb` | Page backgrounds, alternating rows |
| Success BG | `#d1fae5` / `#065f46` | Success badge background/text |
| Warning BG | `#fef3c7` / `#92400e` | Warning badge |
| Danger BG | `#fee2e2` / `#991b1b` | Danger badge |
| Info BG | `#dbeafe` / `#1e40af` | Info badge |

---

**Document Version**: 1.0
**Next Review**: On component library changes