// Run against a local Next.js server with Playwright installed and Chromium available.
// PLAYWRIGHT_MODULE and CHROMIUM_EXECUTABLE allow an existing browser toolchain to be reused.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const origin = new URL(process.env.PERFORMANCE_ORIGIN || 'http://127.0.0.1:3000');
const baseline = process.argv.includes('--baseline');

assert.equal(origin.protocol, 'http:');
assert.ok(['127.0.0.1', 'localhost', '[::1]'].includes(origin.hostname), 'Use a loopback Next.js server');

const session = {
  authenticated: true,
  categories: [],
  rewrite_mode: 'gapgpt',
  session_identity: 'synthetic-performance-test',
  message_visibility_revision: '0',
  free_sends_remaining: 3,
};
const wallet = {
  balance_toman: '1000',
  wallet_terms_version: 'test',
  wallet_enabled: false,
  gateway_enabled: false,
  gateway_configured: false,
  withdrawable: false,
  entries: [],
  topups: [],
};

async function inBrowser(browser, width, fixtures, scenario) {
  const context = await browser.newContext({
    viewport: { width, height: 812 },
    reducedMotion: 'reduce',
    serviceWorkers: 'block',
  });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await context.route('**/api/v1/**', async route => {
    const request = route.request();
    const endpoint = new URL(request.url()).pathname.replace(/^\/api\/v1/, '').replace(/\/$/, '');
    if (request.method() !== 'GET') {
      const mutation = fixtures[`${request.method()} ${endpoint}`];
      if (mutation && new URL(request.url()).origin === origin.origin) {
        await mutation(route);
        return;
      }
      errors.push(`Unexpected API mutation: ${request.method()}`);
      await route.abort();
      return;
    }
    const fixture = fixtures[endpoint];
    await route.fulfill({ json: (typeof fixture === 'function' ? await fixture() : fixture) ?? {} });
  });
  try {
    const result = await scenario(page);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify(result));
  } finally {
    await context.close();
  }
}

async function advance(page, ticks) {
  for (let tick = 0; tick < ticks; tick += 1) {
    await page.clock.runFor(5000);
    // Let an intercepted fetch complete between virtual clock advances.
    await page.waitForTimeout(50);
  }
}

async function checkWallet(browser, mode) {
  let reads = 0;
  let stage = 'initial';
  let resumedReads = 0;
  let releaseRead;
  const holdRead = new Promise(resolve => { releaseRead = resolve; });
  const pendingTopup = { id: 'synthetic-topup', amount_toman: 500, status: 'pending' };
  try {
    await inBrowser(browser, 375, {
      '/bootstrap': session,
      '/wallet': async () => {
        reads += 1;
        if (stage === 'slow') await holdRead;
        if (stage === 'resumed') resumedReads += 1;
        const settled = stage === 'slow' || resumedReads >= 2;
        return {
          ...wallet,
          balance_toman: settled ? '2000' : '1000',
          topups: mode !== 'idle' && !settled ? [pendingTopup] : [],
        };
      },
    }, async page => {
      await page.clock.install();
      await page.addInitScript(() => {
        let hidden = false;
        Object.defineProperty(document, 'hidden', { get: () => hidden });
        window.setSyntheticVisibility = value => {
          hidden = value;
          document.dispatchEvent(new Event('visibilitychange'));
        };
      });
      await page.goto(new URL('/wallet', origin).href);
      await page.getByText('۱٬۰۰۰ تومان', { exact: true }).waitFor();
      await page.waitForTimeout(100);
      const initialReads = reads;
      const refresh = page.getByRole('button', { name: 'تازه‌سازی', exact: true });
      if (mode === 'idle') {
        await advance(page, 25);
        const automatic = reads - initialReads;
        if (!baseline) assert.equal(automatic, 0, 'Idle wallet polling must remain off');
        const response = page.waitForResponse(/\/api\/v1\/wallet\/?$/);
        await refresh.click();
        await response;
        const manual = reads - initialReads - automatic;
        assert.equal(manual, 1);
        return { mode, initialReads, automatic, manual };
      }
      await page.getByText('یک پرداخت در حال بررسی داری.', { exact: false }).waitFor();
      if (mode === 'slow') {
        stage = 'slow';
        await advance(page, 1);
        await refresh.click();
        await advance(page, 1);
        assert.equal(reads - initialReads, 1, 'A slow poll and manual refresh must share one read');
        releaseRead();
        await page.getByText('۲٬۰۰۰ تومان', { exact: true }).waitFor();
        await advance(page, 2);
        assert.equal(reads - initialReads, 1, 'Polling must stop after settlement');
        return { mode, initialReads, readsWhilePending: reads - initialReads };
      }
      await page.evaluate(() => window.setSyntheticVisibility(true));
      await advance(page, 4);
      const hidden = reads - initialReads;
      if (!baseline) assert.equal(hidden, 0, 'Hidden tabs must pause pending wallet polls');
      stage = 'resumed';
      await page.evaluate(() => window.setSyntheticVisibility(false));
      await advance(page, 5);
      await page.getByText('۲٬۰۰۰ تومان', { exact: true }).waitFor();
      if (!baseline) assert.equal(resumedReads, 2);
      return { mode, initialReads, hidden, resumedReads };
    });
  } finally {
    releaseRead();
  }
}

async function checkHome(browser, width) {
  await inBrowser(browser, width, { '/bootstrap': session }, async page => {
    const js = [];
    page.on('response', response => {
      const name = new URL(response.url()).pathname;
      if (name.startsWith('/_next/static/') && name.endsWith('.js')) js.push(response);
    });
    await page.goto(origin.href);
    const proceed = page.getByRole('button', { name: /حرفم رو بگم/ });
    await proceed.waitFor();
    await page.waitForLoadState('networkidle');
    const initialScripts = js.length;
    const bytes = await Promise.all(js.map(async response => (await response.body()).length));
    const hiddenComposerNodes = await page.locator('.compose-slide *').count();
    if (!baseline) assert.equal(hiddenComposerNodes, 0, 'The home page must defer mounting the composer');
    await proceed.click();
    const draft = page.locator('#message-text');
    await draft.waitFor();
    assert.equal(await page.evaluate(() => document.activeElement?.id), 'compose-title');
    const message = 'فقط برای اندازه‌گیری محلی';
    await draft.fill(message);
    await page.waitForLoadState('networkidle');
    const delayedScripts = js.length - initialScripts;
    if (!baseline) assert.ok(delayedScripts > 0, 'Open the composer in a separately loaded chunk');
    await page.evaluate(() => window.history.back());
    await proceed.click();
    assert.equal(await draft.inputValue(), message);
    return { mode: 'home', width, hiddenComposerNodes, initialScripts, initialScriptBytes: bytes.reduce((sum, value) => sum + value, 0), delayedScripts };
  });
}

async function checkTopupRecovery(browser, responseLost) {
  let submissions = 0;
  let settled = false;
  const pending = { id: 'synthetic-recovery', amount_toman: 500, status: 'pending',
    redirect_url: 'https://www.zarinpal.com/pg/StartPay/test' };
  await inBrowser(browser, 375, {
    '/bootstrap': session,
    '/wallet': () => ({ ...wallet, wallet_enabled: true, gateway_enabled: true,
      balance_toman: settled ? '1500' : '1000',
      topups: submissions && !settled ? [pending] : [] }),
    'POST /wallet/topups': route => {
      submissions += 1;
      return responseLost ? route.abort('failed') : route.fulfill({ status: 409,
        json: { error: { code: 'payment_reconciliation', message: 'یک پرداخت باز داری' } } });
    },
  }, async page => {
    await page.clock.install();
    await page.goto(new URL('/wallet', origin).href);
    await page.locator('#wallet-amount').fill('500');
    await page.getByRole('checkbox').check();
    await page.getByRole('button', { name: /شارژ از درگاه/ }).click();
    await page.getByRole('alert').waitFor();
    await advance(page, 2);
    await page.getByRole('button', { name: 'ادامهٔ همان پرداخت' }).waitFor({ timeout: 3000 });
    assert.equal(await page.locator('#wallet-amount').isDisabled(), true);
    settled = true;
    await advance(page, 2);
    await page.getByText('۱٬۵۰۰ تومان', { exact: true }).waitFor();
    assert.equal(submissions, 1, 'Recovery must never repeat a payment POST');
    return { mode: 'topup-recovery', responseLost, submissions };
  });
}

async function checkComposerChunkRecovery(browser) {
  await inBrowser(browser, 375, { '/bootstrap': session }, async page => {
    let rejectScripts = false;
    await page.route('**/_next/static/**/*.js', route => rejectScripts ? route.abort('failed') : route.continue());
    await page.goto(origin.href);
    const proceed = page.getByRole('button', { name: /حرفم رو بگم/ });
    await proceed.waitFor();
    await page.waitForLoadState('networkidle');
    rejectScripts = true;
    await proceed.click();
    await page.getByText('فرم پیام بارگیری نشد.').waitFor({ timeout: 3000 });
    await page.getByRole('button', { name: 'بازگشت', exact: true }).click();
    await proceed.waitFor();
    await proceed.click();
    rejectScripts = false;
    await page.getByRole('button', { name: 'تلاش دوباره', exact: true }).click();
    await page.locator('#message-text').waitFor();
    return { mode: 'composer-chunk-recovery', welcomeAvailable: true, reloadRecovered: true };
  });
}

async function main() {
  const browser = await chromium.launch({ executablePath: process.env.CHROMIUM_EXECUTABLE });
  try {
    await checkWallet(browser, 'idle');
    await checkWallet(browser, 'visibility');
    if (!baseline) await checkWallet(browser, 'slow');
    for (const width of [375, 1280]) await checkHome(browser, width);
    await inBrowser(browser, 375, { '/bootstrap': { ...session, authenticated: false, session_identity: undefined } }, async page => {
      await page.goto(new URL('/#compose', origin).href);
      await page.locator('#sender-phone').waitFor();
      assert.equal(await page.evaluate(() => document.activeElement?.id), 'compose-title');
      return { mode: 'guest-deep-link', phoneFieldVisible: true, headingFocused: true };
    });
    if (!baseline) {
      if (process.argv.includes('--check-chunk-failure')) await checkComposerChunkRecovery(browser);
      await checkTopupRecovery(browser, true);
      await checkTopupRecovery(browser, false);
    }
  } finally {
    await browser.close();
  }
}

main().catch(error => { console.error(error); process.exitCode = 1; });
