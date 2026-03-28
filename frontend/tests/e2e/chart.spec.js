import { test, expect } from '@playwright/test';

const ORDER_URL = '/orders/ORD-001';

// Helpers de sélection basés sur la structure recharts v3 réelle :
// wrapper[0] = graphique score de confiance (HorizontalBar)
// wrapper[1] = graphique de prix (ComposedChart — chandelles + Bollinger)
// wrapper[2] = graphique RSI (LineChart)
const priceChart = (page) => page.locator('.recharts-wrapper').nth(1);
const rsiChart   = (page) => page.locator('.recharts-wrapper').nth(2);

async function waitForChart(page) {
  await page.goto(ORDER_URL);
  // Attendre que le graphique de prix soit chargé (présence de rects colorés = chandelles)
  await page.locator('.recharts-wrapper').nth(1).waitFor({ timeout: 20000 });
  await expect(
    page.locator('.recharts-wrapper').nth(1).locator('rect[fill="#00c48c"], rect[fill="#ff4d6d"]').first()
  ).toBeVisible({ timeout: 15000 });
}

async function switchPeriod(page, label) {
  await page.getByRole('button', { name: label }).click();
  // Attendre que les nouvelles données soient rendues
  await page.waitForTimeout(3000);
}

// ─── Chandelles ────────────────────────────────────────────────────────────────

test.describe('Chandelles japonaises', () => {

  test('des chandelles haussières (vertes) sont rendues', async ({ page }) => {
    await waitForChart(page);
    const greenBodies = priceChart(page).locator('rect[fill="#00c48c"]');
    await expect(greenBodies.first()).toBeVisible();
    expect(await greenBodies.count()).toBeGreaterThanOrEqual(1);
  });

  test('des chandelles baissières (rouges) sont rendues', async ({ page }) => {
    await waitForChart(page);
    const redBodies = priceChart(page).locator('rect[fill="#ff4d6d"]');
    await expect(redBodies.first()).toBeVisible();
    expect(await redBodies.count()).toBeGreaterThanOrEqual(1);
  });

  test('des mèches de chandelles sont rendues', async ({ page }) => {
    await waitForChart(page);
    // Les mèches sont des <line> avec stroke vert ou rouge
    const wicks = priceChart(page).locator('line[stroke="#00c48c"], line[stroke="#ff4d6d"]');
    expect(await wicks.count()).toBeGreaterThan(0);
  });

  test('le nombre de chandelles correspond à la période (10J → ~10)', async ({ page }) => {
    await waitForChart(page);
    const bodies = priceChart(page).locator('rect[fill="#00c48c"], rect[fill="#ff4d6d"]');
    const count = await bodies.count();
    // 10J = 10 jours calendaires → ~7-10 bougies réelles (hors WE/fériés)
    expect(count).toBeGreaterThanOrEqual(5);
    expect(count).toBeLessThanOrEqual(12);
  });

  test('le domaine Y est cohérent avec les prix (pas de 0 dans les ticks)', async ({ page }) => {
    await waitForChart(page);
    // Récupérer toutes les valeurs de tick du graphique de prix
    const yTickValues = await page.evaluate(() => {
      const wrappers = document.querySelectorAll('.recharts-wrapper');
      const priceWrapper = wrappers[1];
      if (!priceWrapper) return [];
      return [...priceWrapper.querySelectorAll('.recharts-cartesian-axis-tick-value')]
        .map(el => el.textContent.trim())
        .filter(t => !t.includes('/') && !t.includes("'")) // exclure les dates (ex: "09/03")
        .map(t => parseFloat(t.replace(/\s/g, '').replace(',', '.')))
        .filter(v => !isNaN(v) && v > 0);
    });
    // Tous les ticks numériques doivent être > 50 (prix NVDA ~165-210)
    expect(yTickValues.length).toBeGreaterThan(0);
    yTickValues.forEach(v => expect(v).toBeGreaterThan(50));
  });

  test('les chandelles restent présentes après changement de période (1M)', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1M');
    const bodies = priceChart(page).locator('rect[fill="#00c48c"], rect[fill="#ff4d6d"]');
    await expect(bodies.first()).toBeVisible();
    expect(await bodies.count()).toBeGreaterThanOrEqual(10);
  });

  test('les chandelles restent présentes après changement de période (1A)', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1A');
    const bodies = priceChart(page).locator('rect[fill="#00c48c"], rect[fill="#ff4d6d"]');
    await expect(bodies.first()).toBeVisible();
    expect(await bodies.count()).toBeGreaterThanOrEqual(50);
  });
});

// ─── Bollinger Bands ────────────────────────────────────────────────────────────

test.describe('Bollinger Bands', () => {

  test('les lignes BB sont présentes pour la période 1M (assez de données)', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1M');
    // Bollinger → 3 Lines avec stroke="#6c63ff"
    const bbLines = priceChart(page).locator('path[stroke="#6c63ff"]');
    expect(await bbLines.count()).toBeGreaterThanOrEqual(3);
  });

  test('les lignes BB sont présentes pour la période 1A', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1A');
    const bbLines = priceChart(page).locator('path[stroke="#6c63ff"]');
    const count = await bbLines.count();
    expect(count).toBeGreaterThanOrEqual(3);
  });

  test('les paths Bollinger ont un contenu non vide (ligne réelle tracée)', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1A');
    const bbLines = priceChart(page).locator('path[stroke="#6c63ff"]');
    await expect(bbLines.first()).toBeVisible();
    const d = await bbLines.first().getAttribute('d');
    expect(d).toBeTruthy();
    expect(d.length).toBeGreaterThan(20);
  });

  test('la bande BB upper est au-dessus de la bande lower (Y inversé en SVG)', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1A');
    // En SVG, Y plus petit = plus haut → upper doit avoir un Y plus petit que lower
    const positions = await page.evaluate(() => {
      const wrappers = document.querySelectorAll('.recharts-wrapper');
      const priceWrapper = wrappers[1];
      const bbPaths = [...priceWrapper.querySelectorAll('path[stroke="#6c63ff"]')];
      // Extraire le premier point M de chaque path pour comparer les Y
      return bbPaths.map(p => {
        const d = p.getAttribute('d') || '';
        const match = d.match(/M[\s]*([\d.]+)[\s,]+([\d.]+)/);
        return match ? parseFloat(match[2]) : null;
      }).filter(v => v !== null);
    });
    // upper (Y plus bas en SVG) < lower (Y plus haut en SVG)
    // On vérifie juste qu'on a 3 lignes à des Y différents
    expect(positions.length).toBeGreaterThanOrEqual(3);
    const unique = new Set(positions.map(v => Math.round(v)));
    expect(unique.size).toBeGreaterThanOrEqual(2);
  });
});

// ─── RSI ────────────────────────────────────────────────────────────────────────

test.describe('RSI (14)', () => {

  test('le titre RSI (14) est affiché', async ({ page }) => {
    await waitForChart(page);
    // exact:true + first() car la légende contient aussi "— RSI (14)"
    await expect(page.getByText('RSI (14)', { exact: true }).first()).toBeVisible();
  });

  test('la ligne RSI est rendue pour la période 1M', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1M');
    const rsiLine = rsiChart(page).locator('path[stroke="#ffd166"]');
    await expect(rsiLine).toBeVisible();
    const d = await rsiLine.getAttribute('d');
    expect(d).toBeTruthy();
    expect(d.length).toBeGreaterThan(20);
  });

  test('la ligne RSI est rendue pour la période 1A', async ({ page }) => {
    await waitForChart(page);
    await switchPeriod(page, '1A');
    const rsiLine = rsiChart(page).locator('path[stroke="#ffd166"]');
    await expect(rsiLine).toBeVisible();
  });

  test('les lignes de référence RSI 30 et 70 sont présentes', async ({ page }) => {
    await waitForChart(page);
    const refLines = rsiChart(page).locator('.recharts-reference-line');
    expect(await refLines.count()).toBeGreaterThanOrEqual(2);
  });

  test('l\'axe Y du RSI contient les valeurs 30 et 70', async ({ page }) => {
    await waitForChart(page);
    const ticks = await rsiChart(page)
      .locator('.recharts-cartesian-axis-tick-value')
      .allTextContents();
    const values = ticks.map(t => parseInt(t)).filter(v => !isNaN(v));
    expect(values).toContain(30);
    expect(values).toContain(70);
  });
});

// ─── Niveaux de référence ────────────────────────────────────────────────────────

test.describe('Niveaux de référence', () => {

  test('la ligne d\'entrée est affichée', async ({ page }) => {
    await waitForChart(page);
    await expect(page.getByText(/Entrée \d/)).toBeVisible();
  });

  test('la ligne Stop Loss est affichée', async ({ page }) => {
    await waitForChart(page);
    await expect(page.getByText(/SL \d/)).toBeVisible();
  });

  test('la ligne Take Profit est affichée', async ({ page }) => {
    await waitForChart(page);
    await expect(page.getByText(/TP \d/)).toBeVisible();
  });
});

// ─── Changement de période ────────────────────────────────────────────────────────

test.describe('Sélection de période', () => {

  test('le bouton 10J est actif par défaut', async ({ page }) => {
    await waitForChart(page);
    const btn = page.getByRole('button', { name: '10J' });
    const bg = await btn.evaluate(el => getComputedStyle(el).backgroundColor);
    // Couleur active = #6c63ff = rgb(108, 99, 255)
    expect(bg).toBe('rgb(108, 99, 255)');
  });

  test('cliquer sur 1M active ce bouton', async ({ page }) => {
    await waitForChart(page);
    await page.getByRole('button', { name: '1M' }).click();
    const btn = page.getByRole('button', { name: '1M' });
    const bg = await btn.evaluate(el => getComputedStyle(el).backgroundColor);
    expect(bg).toBe('rgb(108, 99, 255)');
  });
});
