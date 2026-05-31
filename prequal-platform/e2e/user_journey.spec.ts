import { test, expect } from '@playwright/test';

const testEmail = `e2e${Date.now()}@test.com`;
const testPassword = 'TestPassword123!';
const testCompanyName = `E2E Test Company ${Date.now()}`;

test.describe('Primary User Journey', () => {
  test('complete flow: registration -> login -> add subcontractor -> view compliance', async ({ page }) => {
    // Step 1: User Registration
    await page.goto('/register');
    await page.getByLabel('Email').fill(testEmail);
    await page.getByLabel('Password').fill(testPassword);
    await page.getByRole('button', { name: 'Register' }).click();

    // Should redirect to dashboard after successful registration
    await expect(page).toHaveURL(/\/(dashboard)?$/);
    await expect(page.getByText('Dashboard')).toBeVisible({ timeout: 10000 });

    // Step 2: Add Subcontractor
    await page.getByRole('link', { name: 'Subcontractors' }).or(page.getByText('Add Subcontractor')).first().click();
    await page.waitForURL(/\/subcontractors/);

    // Click add subcontractor button
    await page.getByRole('button', { name: /add subcontractor/i }).or(
      page.locator('a[href="/subcontractors/new"]')
    ).first().click();

    // Fill in subcontractor form
    await page.waitForSelector('input[name="company_name"]', { timeout: 5000 }).catch(() => {
      // Form might be on a different route
    });

    const companyInput = page.locator('input[name="company_name"]');
    if (await companyInput.isVisible()) {
      await companyInput.fill(testCompanyName);
      await page.locator('input[name="email"]').fill(`sub-${testEmail}`);
      await page.locator('input[name="phone"]').fill('555-0100');
      await page.locator('input[name="address_line1"]').fill('123 Main St');
      await page.locator('input[name="city"]').fill('Austin');
      await page.locator('input[name="state"]').fill('TX');
      await page.locator('input[name="zip_code"]').fill('78701');
      
      await page.getByRole('button', { name: /save|create|submit/i }).click();
    }

    // Step 3: View Compliance (Dashboard)
    await page.goto('/dashboard');
    await expect(page.getByText('Dashboard')).toBeVisible({ timeout: 10000 });

    // Verify dashboard shows metrics
    await expect(page.getByText(/Total Subcontractors|Compliance Rate/i)).toBeVisible({ timeout: 10000 });

    // Step 4: Verify Subcontractor Appears in List
    await page.goto('/subcontractors');
    await expect(page.getByText(testCompanyName).or(page.getByText(`sub-${testEmail}`))).toBeVisible({ timeout: 10000 });
  });

  test('login with valid credentials', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill(testEmail);
    await page.getByLabel('Password').fill(testPassword);
    await page.getByRole('button', { name: 'Login' }).click();

    await expect(page).toHaveURL(/\/(dashboard)?$/);
    await expect(page.getByText('Dashboard')).toBeVisible({ timeout: 10000 });
  });

  test('login with invalid credentials shows error', async ({ page }) => {
    await page.goto('/login');
    await page.getByLabel('Email').fill('wrong@test.com');
    await page.getByLabel('Password').fill('wrongpassword');
    await page.getByRole('button', { name: 'Login' }).click();

    await expect(page.getByText(/invalid|incorrect|401|unauthorized/i)).toBeVisible({ timeout: 5000 });
  });
});