import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test.afterEach(async({page,baseURL})=>{await page.unrouteAll({behavior:'ignoreErrors'});const me=await page.request.get('/api/v1/auth/me');if(me.ok()){const session=await me.json();await page.request.post('/api/v1/auth/logout',{headers:{Origin:baseURL,'X-CSRF-Token':session.csrf},data:{}});}});
for(const mode of ['light','dark']) for(const width of [320,390,768,1024,1440]) test(`simulation flows and accessibility in ${mode} at ${width}`,async({page})=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.setViewportSize({width,height:1000});await page.goto('/');
 await expect(page).toHaveTitle('Onesa Robot — Software simulation');
 await page.locator('.appearance-control select').selectOption(mode);
 await expect(page.locator('html')).toHaveAttribute('data-theme',mode);
 await page.keyboard.press('Tab');
 await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
 await page.getByLabel('Operator name').fill(process.env.ROBOT_TEST_OPERATOR || 'operator');await page.getByLabel('Password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();await page.reload();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByLabel('Confirm password to reset').fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Reset simulation stop'}).click();
 await expect(page.locator('#stop-state')).toContainText('Ready');
 await page.getByRole('button',{name:'Create proposal'}).click();await expect(page.locator('#approval-form')).toBeVisible();await expect(page.locator('#proposed-id')).toContainText(/[a-f0-9-]{36}/);const taskId=await page.locator('#proposed-id').textContent();await page.getByLabel('Confirm operator password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Approve simulation task'}).click();
 await expect(page.locator('#history li').filter({hasText:taskId})).toContainText('completed',{timeout:6000});
 await page.getByRole('button',{name:'Stop simulation',exact:true}).click();await expect(page.locator('#stop-state')).toContainText('Stopped');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 const axe=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze();expect(axe.violations).toEqual([]);
 await page.getByRole('button',{name:'Sign out'}).click();await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 expect(errors).toEqual([]);
});
test('late unauthorized telemetry cannot sign out a newer operator session',async({page})=>{
 let held, release;
 const received=new Promise(resolve=>held=resolve);
 const wait=new Promise(resolve=>release=resolve);
 await page.route('**/api/v1/status',async route=>{
  if(!held){await route.continue();return;}
  const signal=held;held=null;signal();await wait;
  await route.fulfill({status:401,contentType:'application/json',body:'{"detail":"Old session expired"}'});
 });
 await page.goto('/');
 async function signIn(){await page.getByLabel('Operator name').fill(process.env.ROBOT_TEST_OPERATOR || 'operator');await page.getByLabel('Password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();}
 await signIn();await received;
 await page.getByRole('button',{name:'Sign out'}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await signIn();release();
 await expect(page.locator('#connection')).toHaveText('Connected to software simulator');
 await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByRole('button',{name:'Sign out'}).click();
});
