import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import userEvent from '@testing-library/user-event';
import {
  Button,
  Input,
  Textarea,
  Select,
  Checkbox,
  Badge,
  Card,
  Modal,
  Alert,
  Table,
  Tooltip,
  Avatar,
} from '../components/ui';

describe('Button', () => {
  test('renders children and fires onClick', async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();
    render(<Button onClick={onClick}>Save Changes</Button>);

    await user.click(screen.getByRole('button', { name: 'Save Changes' }));
    expect(onClick).toHaveBeenCalledTimes(1);
  });

  test('does not fire onClick when disabled or loading', async () => {
    const user = userEvent.setup();
    const onClick = jest.fn();
    const { rerender } = render(<Button onClick={onClick} disabled>Submit</Button>);

    await user.click(screen.getByRole('button', { name: 'Submit' }));
    expect(onClick).not.toHaveBeenCalled();

    rerender(<Button onClick={onClick} loading>Submit</Button>);
    await user.click(screen.getByRole('button', { name: 'Submit' }));
    expect(onClick).not.toHaveBeenCalled();
  });
});

describe('Input', () => {
  test('associates label with input via htmlFor/id', () => {
    render(<Input label="Company Name" />);

    const input = screen.getByLabelText('Company Name');
    expect(input).toBeInTheDocument();
    expect(input.tagName).toBe('INPUT');
  });

  test('error state sets aria-invalid and links error message with role=alert', () => {
    render(<Input label="Email" error="Email is required" />);

    const input = screen.getByLabelText('Email');
    expect(input).toHaveAttribute('aria-invalid', 'true');

    const errorId = input.getAttribute('aria-describedby');
    expect(errorId).toBeTruthy();
    const errorMessage = document.getElementById(errorId);
    expect(errorMessage).toHaveAttribute('role', 'alert');
    expect(errorMessage).toHaveTextContent('Email is required');
  });

  test('hint is linked via aria-describedby when no error', () => {
    render(<Input label="Email" hint="We never share your email" />);

    const input = screen.getByLabelText('Email');
    const hintId = input.getAttribute('aria-describedby');
    const hint = document.getElementById(hintId);
    expect(hint).toHaveTextContent('We never share your email');
  });

  test('respects consumer-provided id', () => {
    render(<Input id="custom-id" label="Field" />);
    expect(screen.getByLabelText('Field')).toHaveAttribute('id', 'custom-id');
  });
});

describe('Textarea', () => {
  test('associates label and reports errors accessibly', () => {
    render(<Textarea label="Notes" error="Notes are too long" />);

    const textarea = screen.getByLabelText('Notes');
    expect(textarea.tagName).toBe('TEXTAREA');
    expect(textarea).toHaveAttribute('aria-invalid', 'true');

    const errorId = textarea.getAttribute('aria-describedby');
    expect(document.getElementById(errorId)).toHaveAttribute('role', 'alert');
  });
});

describe('Select', () => {
  const options = [
    { value: 'compliant', label: 'Compliant' },
    { value: 'pending', label: 'Pending Review' },
    { value: 'expired', label: 'Expired' },
  ];

  test('opens listbox on click and selects via keyboard', () => {
    const onChange = jest.fn();
    function ControlledSelect() {
      const [value, setValue] = React.useState(undefined);
      return (
        <Select
          label="Status"
          options={options}
          value={value}
          onChange={(v) => {
            setValue(v);
            onChange(v);
          }}
        />
      );
    }
    render(<ControlledSelect />);

    const trigger = screen.getByLabelText('Status');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');

    fireEvent.click(trigger);
    expect(trigger).toHaveAttribute('aria-expanded', 'true');
    expect(screen.getByRole('listbox')).toBeInTheDocument();

    fireEvent.keyDown(trigger, { key: 'ArrowDown' });
    fireEvent.keyDown(trigger, { key: 'Enter' });

    expect(onChange).toHaveBeenCalledWith('compliant');
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(trigger).toHaveTextContent('Compliant');
  });

  test('closes on Escape without selecting', () => {
    const onChange = jest.fn();
    render(<Select label="Status" options={options} onChange={onChange} />);

    const trigger = screen.getByLabelText('Status');
    fireEvent.click(trigger);
    fireEvent.keyDown(trigger, { key: 'Escape' });

    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(onChange).not.toHaveBeenCalled();
  });

  test('error state is announced via role=alert and aria-invalid', () => {
    render(<Select label="Status" options={options} error="Pick a status" />);

    const trigger = screen.getByLabelText('Status');
    expect(trigger).toHaveAttribute('aria-invalid', 'true');

    const errorId = trigger.getAttribute('aria-describedby');
    expect(document.getElementById(errorId)).toHaveAttribute('role', 'alert');
  });
});

describe('Checkbox', () => {
  test('toggles through the label and reports checked state', async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    const { rerender } = render(<Checkbox label="Accept terms" checked={false} onChange={onChange} />);

    const checkbox = screen.getByLabelText('Accept terms');
    await user.click(checkbox);
    expect(onChange).toHaveBeenLastCalledWith(true);

    rerender(<Checkbox label="Accept terms" checked onChange={onChange} />);
    expect(screen.getByLabelText('Accept terms')).toBeChecked();
  });

  test('does not change when disabled', async () => {
    const user = userEvent.setup();
    const onChange = jest.fn();
    render(<Checkbox label="Locked" disabled onChange={onChange} />);

    await user.click(screen.getByLabelText('Locked'));
    expect(onChange).not.toHaveBeenCalled();
  });
});

describe('Modal', () => {
  test('renders with dialog semantics and closes on Escape', () => {
    const onClose = jest.fn();
    render(
      <Modal isOpen onClose={onClose} title="Confirm deletion">
        Delete this subcontractor?
      </Modal>
    );

    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-labelledby', 'modal-title');
    expect(screen.getByText('Delete this subcontractor?')).toBeInTheDocument();

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('close button has accessible name and fires onClose', async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    render(<Modal isOpen onClose={onClose} title="Title">Body</Modal>);

    await user.click(screen.getByRole('button', { name: 'Close modal' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  test('traps Tab focus within the dialog', () => {
    render(
      <Modal isOpen onClose={() => {}} title="Title" footer={<Button>Confirm</Button>}>
        Body
      </Modal>
    );

    const closeButton = screen.getByRole('button', { name: 'Close modal' });
    const confirmButton = screen.getByRole('button', { name: 'Confirm' });

    confirmButton.focus();
    fireEvent.keyDown(document, { key: 'Tab' });
    expect(closeButton).toHaveFocus();

    fireEvent.keyDown(document, { key: 'Tab', shiftKey: true });
    expect(confirmButton).toHaveFocus();
  });

  test('moves focus into the dialog on open and restores it on close', () => {
    const outsideButton = document.createElement('button');
    outsideButton.textContent = 'Outside';
    document.body.appendChild(outsideButton);
    outsideButton.focus();

    const { rerender, unmount } = render(
      <Modal isOpen onClose={() => {}} title="Title">Body</Modal>
    );

    expect(screen.getByRole('button', { name: 'Close modal' })).toHaveFocus();

    rerender(<Modal isOpen={false} onClose={() => {}} title="Title">Body</Modal>);
    expect(outsideButton).toHaveFocus();

    unmount();
    document.body.removeChild(outsideButton);
  });
});

describe('Tooltip', () => {
  test('shows on trigger focus with role=tooltip and aria-describedby link', () => {
    render(
      <Tooltip content="Delete this subcontractor">
        <button>Delete</button>
      </Tooltip>
    );

    const trigger = screen.getByRole('button', { name: 'Delete' });
    fireEvent.focus(trigger);

    const tooltip = screen.getByRole('tooltip');
    expect(tooltip).toHaveTextContent('Delete this subcontractor');
    expect(trigger).toHaveAttribute('aria-describedby', tooltip.getAttribute('id'));

    fireEvent.blur(trigger);
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument();
  });
});

describe('Alert', () => {
  test('renders with role=alert and dismiss button', async () => {
    const user = userEvent.setup();
    const onClose = jest.fn();
    render(
      <Alert variant="warning" title="Expiring certifications" onClose={onClose}>
        3 certifications expire next week
      </Alert>
    );

    expect(screen.getByRole('alert')).toHaveTextContent('3 certifications expire next week');
    expect(screen.getByText('Expiring certifications')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Dismiss' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });
});

describe('Badge', () => {
  test('renders children', () => {
    render(<Badge variant="success">Compliant</Badge>);
    expect(screen.getByText('Compliant')).toBeInTheDocument();
  });
});

describe('Card', () => {
  test('renders title, description, action, and content slots', () => {
    render(
      <Card title="Compliance Summary" description="Last 30 days" action={<Button>Export</Button>}>
        <span>Card body</span>
      </Card>
    );

    expect(screen.getByText('Compliance Summary')).toBeInTheDocument();
    expect(screen.getByText('Last 30 days')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Export' })).toBeInTheDocument();
    expect(screen.getByText('Card body')).toBeInTheDocument();
  });
});

describe('Avatar', () => {
  test('falls back to initials with img role and accessible name', () => {
    render(<Avatar name="Jane Doe" />);

    const avatar = screen.getByRole('img', { name: 'Jane Doe' });
    expect(avatar).toHaveTextContent('JD');
  });
});

describe('Table', () => {
  const columns = [
    { key: 'name', header: 'Company', sortable: true },
    {
      key: 'status',
      header: 'Status',
      render: (value) => <Badge variant={value === 'compliant' ? 'success' : 'danger'}>{String(value)}</Badge>,
    },
  ];
  const data = [
    { id: '1', name: 'Acme Roofing', status: 'compliant' },
    { id: '2', name: 'Best Electrical', status: 'expired' },
  ];

  test('renders headers and rows, and fires onRowClick', async () => {
    const user = userEvent.setup();
    const onRowClick = jest.fn();
    render(<Table columns={columns} data={data} keyExtractor={(row) => row.id} onRowClick={onRowClick} />);

    expect(screen.getByText('Company')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
    expect(screen.getByText('Acme Roofing')).toBeInTheDocument();
    expect(screen.getByText('Best Electrical')).toBeInTheDocument();
    expect(screen.getByText('compliant')).toBeInTheDocument();
    expect(screen.getByText('expired')).toBeInTheDocument();

    await user.click(screen.getByText('Acme Roofing'));
    expect(onRowClick).toHaveBeenCalledWith(expect.objectContaining({ id: '1', name: 'Acme Roofing' }));
  });

  test('shows empty message when there is no data', () => {
    render(<Table columns={columns} data={[]} keyExtractor={(row) => row.id} emptyMessage="No subcontractors yet" />);

    expect(screen.getByText('No subcontractors yet')).toBeInTheDocument();
  });
});
