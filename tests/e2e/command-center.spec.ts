import {expect, Page, test} from '@playwright/test';

const email = process.env.NOVENA_E2E_EMAIL;
const password = process.env.NOVENA_E2E_PASSWORD;
const teamSlug = process.env.NOVENA_E2E_TEAM || 'pilot-cold-room';

async function signIn(page: Page): Promise<void> {
  await page.goto('/accounts/login/');
  await page.locator('input[name="login"]').fill(email || '');
  await page.locator('input[name="password"]').fill(password || '');
  await page.locator('input[type="submit"]').click();
  await page.waitForURL(url => !url.pathname.includes('/accounts/login/'));
}

async function resetPersonalLayout(page: Page): Promise<void> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    await page.goto(`/a/${teamSlug}/`);
    const status = await page.evaluate(async () => {
      const configNode = document.getElementById('command-center-config');
      if (!configNode?.textContent) return 204;
      const config = JSON.parse(configNode.textContent);
      const csrf = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/)?.[1] || '';
      const response = await fetch(config.urls.reset, {
        method: 'POST',
        headers: {'Content-Type': 'application/json', 'X-CSRFToken': decodeURIComponent(csrf)},
        body: JSON.stringify({base_revision: config.personal_revision}),
      });
      return response.status;
    });
    if (status === 200 || status === 204) return;
    if (status !== 409 || attempt === 1) throw new Error(`Layout reset failed with ${status}`);
  }
}

async function expectVisiblePanelsToFit(page: Page): Promise<void> {
  const geometry = await page.locator('#command-center-grid').evaluate(grid => {
    const gridBox = grid.getBoundingClientRect();
    const panels = Array.from(grid.querySelectorAll<HTMLElement>('[data-panel-id]'))
      .filter(panel => !panel.hidden)
      .map(panel => {
        const box = panel.getBoundingClientRect();
        return {id: panel.dataset.panelId, left: box.left, top: box.top, right: box.right, bottom: box.bottom};
      });
    return {grid: {left: gridBox.left, right: gridBox.right}, panels};
  });
  for (const panel of geometry.panels) {
    expect(panel.left).toBeGreaterThanOrEqual(geometry.grid.left - 1);
    expect(panel.right).toBeLessThanOrEqual(geometry.grid.right + 1);
  }
  for (let left = 0; left < geometry.panels.length; left += 1) {
    for (let right = left + 1; right < geometry.panels.length; right += 1) {
      const a = geometry.panels[left];
      const b = geometry.panels[right];
      const overlaps = a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
      expect(overlaps, `${a.id} overlaps ${b.id}`).toBe(false);
    }
  }
}

test.beforeEach(async ({page}) => {
  test.skip(!email || !password, 'Set NOVENA_E2E_EMAIL and NOVENA_E2E_PASSWORD to run authenticated UI checks.');
  await page.addInitScript(() => {
    document.addEventListener('DOMContentLoaded', () => {
      const style = document.createElement('style');
      style.textContent = '#djDebug { display: none !important; }';
      document.head.append(style);
    });
  });
  await signIn(page);
  await page.goto(`/a/${teamSlug}/`);
  await expect(page.getByRole('heading', {name: 'Command Center'})).toBeVisible();
});

test.afterEach(async ({page}) => {
  if (!email || !password) return;
  await resetPersonalLayout(page);
});

test('desktop supports draft resize, hide, cancel, save, restore, and refresh', async ({page}, testInfo) => {
  test.skip(testInfo.project.name !== 'desktop');
  await expect(page.locator('[data-fixed-kpi-strip] > a')).toHaveCount(5);
  await page.getByRole('button', {name: 'Customize'}).click();
  await page.locator('[data-fixed-kpi-strip] > a').first().click();
  await expect(page).toHaveURL(new RegExp(`/a/${teamSlug}/?$`));
  await expect(page.locator('#dashboard-live-container')).toBeVisible();
  await expect(page.getByRole('button', {name: 'Save'})).toBeVisible();
  const firstPanel = page.locator('#command-center-grid > .grid-stack-item').first();
  for (const direction of ['n', 'e', 's', 'w', 'ne', 'nw', 'se', 'sw']) {
    await expect(firstPanel.locator(`.ui-resizable-${direction}`)).toHaveCount(1);
  }

  const attention = page.locator('[data-panel-id="needs_attention"]');
  await attention.getByRole('button', {name: 'Needs Attention options'}).click();
  await attention.getByRole('button', {name: 'Expanded'}).click();
  await expect(attention).toHaveAttribute('data-density', 'expanded');

  const assetMix = page.locator('[data-panel-id="asset_mix"]');
  await assetMix.getByRole('button', {name: 'Asset Mix options'}).click();
  await assetMix.getByRole('button', {name: 'Hide'}).click();
  await expect(page.locator('#command-center-hidden-count')).toHaveText('1');
  await expectVisiblePanelsToFit(page);
  await page.screenshot({path: testInfo.outputPath('desktop-edit.png'), fullPage: true});

  await page.getByRole('button', {name: 'Cancel'}).click();
  await expect(assetMix).toBeVisible();
  await page.getByRole('button', {name: 'Customize'}).click();
  await assetMix.getByRole('button', {name: 'Asset Mix options'}).click();
  await assetMix.getByRole('button', {name: 'Hide'}).click();
  await page.getByRole('button', {name: 'Save'}).click();
  await page.reload();
  await expect(page.locator('[data-panel-id="asset_mix"]')).toBeHidden();

  await page.getByRole('button', {name: 'Customize'}).click();
  await page.getByRole('button', {name: /Add panels/}).click();
  await page.locator('[data-panel-catalog-id="asset_mix"]').getByRole('button', {name: 'Add'}).click();
  await expect(page.locator('[data-panel-id="asset_mix"]')).toBeVisible();
  await page.getByRole('button', {name: 'Cancel'}).click();

  const refresh = page.getByRole('button', {name: 'Refresh fleet summary now'});
  await refresh.click();
  await expect(refresh).toBeEnabled({timeout: 15_000});
});

test('Needs Attention hide requires an operational warning', async ({page}) => {
  await page.getByRole('button', {name: 'Customize'}).click();
  const attention = page.locator('[data-panel-id="needs_attention"]');
  await attention.getByRole('button', {name: 'Needs Attention options'}).click();
  await attention.getByRole('button', {name: 'Hide'}).click();
  await expect(page.getByRole('heading', {name: 'Hide Needs Attention?'})).toBeVisible();
  await expect(page.locator('[data-fixed-kpi-strip]')).toBeVisible();
  await page.getByRole('button', {name: 'Cancel'}).last().click();
});

test('mobile uses single-column ordering controls without resize handles', async ({page}, testInfo) => {
  test.skip(testInfo.project.name !== 'mobile');
  await page.getByRole('button', {name: 'Customize'}).click();
  await expect(page.locator('#command-center-grid')).toHaveClass(/command-center-mobile-grid/);
  await expect(page.locator('.ui-resizable-handle')).toHaveCount(0);
  const gridWidth = await page.locator('#command-center-grid').evaluate(element => element.getBoundingClientRect().width);
  expect(gridWidth).toBeGreaterThanOrEqual(280);
  const attention = page.locator('[data-panel-id="needs_attention"]');
  await attention.getByRole('button', {name: 'Needs Attention options'}).click();
  await attention.getByRole('button', {name: 'Move earlier'}).click();
  await expectVisiblePanelsToFit(page);
  await page.screenshot({path: testInfo.outputPath('mobile-edit.png'), fullPage: true});
});

test('admin can publish and remove a team default', async ({page}) => {
  const actions = page.locator('#command-center-actions');
  await actions.locator('summary').click();
  const publish = page.getByRole('button', {name: 'Publish as team default'});
  test.skip(!(await publish.count()), 'Authenticated user cannot manage the team.');
  await publish.click();
  await page.getByRole('button', {name: 'Publish default'}).click();
  await expect(page.locator('.command-center-toast', {hasText: 'Team default published.'})).toBeVisible();
  await actions.locator('summary').click();
  await page.getByRole('button', {name: 'Remove team default'}).click();
  await page.getByRole('button', {name: 'Remove default'}).click();
  await expect(page.locator('.command-center-toast', {hasText: 'Team default removed.'})).toBeVisible();
});
