/* Read/write only the explicitly authorized isolated demo; never point at a live site. */
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const {chromium} = require(process.env.PLAYWRIGHT_PACKAGE || 'playwright');
const origin = 'http://127.0.0.1:3137';
const result = {sourceVersion:'0.16.1', checks:[], pageErrors:[], externalRequests:[], physicalDevice:false, productionPWA:false};
(async()=>{
  const boot = await (await fetch(origin+'/api/v1/bootstrap')).json();
  assert.equal(boot.demo_mode,true); assert.equal(boot.otp_is_real,false);
  assert.equal(boot.rewrite_mode,'template'); assert.equal(boot.payment_backend,'demo');
  const browser = await chromium.launch({headless:true, ...(process.env.CHROME_EXECUTABLE?{executablePath:process.env.CHROME_EXECUTABLE}:{})});
  try {
    for (const [width,phone,recipient] of [[375,'09000000006','09000000008'],[1600,'09000000007','09000000009']]) {
      const context = await browser.newContext({viewport:{width,height:width===375?844:1000},deviceScaleFactor:width===375?2:1,isMobile:width===375,hasTouch:width===375,colorScheme:'dark',reducedMotion:'reduce'});
      await context.route('**/*', route=>{
        const u=new URL(route.request().url());
        if(u.origin===origin)return route.continue();
        result.externalRequests.push(u.origin); return route.abort();
      });
      const page=await context.newPage(); page.setDefaultTimeout(8000);
      page.on('pageerror',error=>result.pageErrors.push(error.message));
      await page.goto(origin+'/#compose');
      await page.locator('#sender-phone').fill(phone);
      const otp=page.waitForResponse(r=>r.url().endsWith('/auth/request-otp'));
      await page.getByRole('button',{name:'دریافت کد تأیید',exact:true}).click();
      const code=(await(await otp).json()).debug_code; assert.ok(code);
      await page.locator('#otp-code').fill(code);
      await page.locator('#message-text').waitFor();
      await page.locator('#message-text').fill('از وقتی که برای همکاری گذاشتی ممنونم.');
      await page.getByRole('button',{name:'بعدی؛ متن نهایی و ارسال',exact:true}).click();
      const field=await page.locator('#message-error').innerText();
      assert.match(field,/بازنویسی متن دلخواه هنوز فعال نیست/);
      result.checks.push({width,check:'template mode blocks arbitrary freeform',pass:true});
      if(width===375){
        await page.locator('#message-text').blur();
        await page.screenshot({path:path.join(__dirname,'qa-freeform-unavailable.png'),animations:'disabled'});
      }
      await page.getByRole('button',{name:'حال خوب',exact:true}).click();
      await page.getByRole('button',{name:'تشکر و قدردانی',exact:true}).click();
      await page.getByRole('button',{name:'بعدی؛ متن نهایی و ارسال',exact:true}).click();
      await page.locator('#quote-recipient').fill('۰۹');
      await page.getByRole('button',{name:'آماده‌سازی متن',exact:true}).click();
      assert.match(await page.locator('#quote-recipient-error').innerText(),/۱۱ رقم/);
      assert.equal(await page.locator('#quote-recipient').inputValue(),'09');
      result.checks.push({width,check:'incomplete recipient rejected; Persian input canonicalized',pass:true});
      await page.locator('#quote-recipient').fill(recipient);
      await page.getByRole('button',{name:'آماده‌سازی متن',exact:true}).click();
      await page.getByText('متن آمادهٔ بررسی‌شده',{exact:true}).waitFor();
      const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
      assert.equal(overflow,false); result.checks.push({width,check:'preview horizontal overflow',pass:true});
      await page.locator('#respect-consent').check();
      await page.getByRole('button',{name:'ارسال رایگان آزمایشی',exact:true}).click();
      await page.getByText('درخواست آزمایشی ثبت شد.',{exact:true}).waitFor();
      await page.goto(origin+'/history');
      await page.getByText('ارسال شبیه‌سازی شد · آزمایشی',{exact:true}).waitFor();
      await page.getByRole('button',{name:'تازه‌سازی',exact:true}).click();
      result.checks.push({width,check:'simulated order, receipt, history and explicit refresh',pass:true});
      await page.goto(origin+'/preferences');
      await page.getByRole('button',{name:'توقف دریافت تمام پیام‌ها',exact:true}).click();
      await page.getByText('دریافت پیام متوقف شده',{exact:true}).waitFor();
      await page.getByRole('button',{name:'فعال‌کردن دوباره دریافت پیام',exact:true}).click();
      await page.getByText('دریافت پیام فعاله',{exact:true}).waitFor();
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      result.checks.push({width,check:'own-number stop/resume with recent OTP and no horizontal overflow',pass:true});
      await page.keyboard.press('Tab');
      result.checks.push({width,check:'keyboard focus reachable',pass:await page.evaluate(()=>document.activeElement!==document.body)});
      await context.close();
    }
    assert.equal(result.pageErrors.length,0);
    result.completedAt=new Date().toISOString(); result.status='passed';
  } finally {
    await browser.close();
    fs.writeFileSync(path.join(__dirname,'browser-checks.json'),JSON.stringify(result,null,2)+'\n');
  }
  console.log(JSON.stringify(result,null,2));
})().catch(error=>{console.error(error.message);process.exitCode=1;});
