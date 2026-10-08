import { test, expect } from '@playwright/test';

test('POS login screen loads', async ({ page }) => {
  await page.goto('/');
  await expect(page.getByText('Lovely Tech')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Login' })).toBeVisible();
});
