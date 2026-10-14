import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
test.afterEach(async({page,baseURL})=>{await page.unrouteAll({behavior:'ignoreErrors'});const me=await page.request.get('/api/v1/auth/me');if(me.ok()){const session=await me.json();await page.request.post('/api/v1/auth/logout',{headers:{Origin:baseURL,'X-CSRF-Token':session.csrf},data:{}});}});
for(const [hour,mode] of [[20,'light'],[12,'dark']]) for(const width of [320,390,768,1024,1440]) test(`simulation ${mode} flows and accessibility at ${width}`,async({page})=>{
 await page.addInitScript(hour=>{Date.prototype.getHours=()=>hour;},hour);
 const errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.emulateMedia({colorScheme:mode});await page.setViewportSize({width,height:1000});await page.goto('/console');
 await expect(page).toHaveTitle('Operator Console | Onesa AI Robot');
 await expect(page.locator('.appearance-control')).toHaveCount(0);
 expect(await page.evaluate(()=>getComputedStyle(document.documentElement).colorScheme)).toBe(mode);
 expect(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor)).toBe(mode==='dark'?'rgb(11, 21, 35)':'rgb(255, 255, 255)');
 await page.keyboard.press('Tab');
 await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();
 await page.getByLabel('Operator name').fill(process.env.ROBOT_TEST_OPERATOR || 'operator');await page.getByLabel('Password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();for(let navigation=0;navigation<3;navigation++){await page.reload();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();}
 await page.getByLabel('Confirm password to reset').fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Reset simulation stop'}).click();
 await expect(page.locator('#stop-state')).toContainText('Ready');
 await page.getByRole('button',{name:'Create proposal'}).click();await expect(page.locator('#approval-form')).toBeVisible();await expect(page.locator('#proposed-id')).toContainText(/[a-f0-9-]{36}/);const taskId=await page.locator('#proposed-id').textContent();await page.getByLabel('Confirm operator password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Approve simulation task'}).click();
 await expect(page.locator('#history li').filter({hasText:taskId})).toContainText('completed',{timeout:6000});
 await page.getByRole('button',{name:'Stop simulation',exact:true}).click();await expect(page.locator('#stop-state')).toContainText('Stopped');
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
 if(process.env.ONESA_VISUAL_EVIDENCE_DIR&&[390,1440].includes(width))await page.screenshot({path:`${process.env.ONESA_VISUAL_EVIDENCE_DIR}/${test.info().project.name}/robot-console-${mode}-${width}.png`,fullPage:true});
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
 await page.goto('/console');
 async function signIn(){await page.getByLabel('Operator name').fill(process.env.ROBOT_TEST_OPERATOR || 'operator');await page.getByLabel('Password',{exact:true}).fill((process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only'));await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();}
 await signIn();await received;
 await page.getByRole('button',{name:'Sign out'}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await signIn();release();
 await expect(page.locator('#connection')).toHaveText('Connected to software simulator');
 await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByRole('button',{name:'Sign out'}).click();
});
for(const mode of ['light','dark'])for(const width of [320,390,768,1024,1440])test(`public Robot identity and telemetry isolation ${mode} at ${width}`,async({page})=>{
 await page.emulateMedia({colorScheme:mode});await page.setViewportSize({width,height:1000});const privateRequests=[];page.on('request',request=>{if(request.url().includes('/api/v1/'))privateRequests.push(request.url());});
 await page.goto('/');await expect(page).toHaveTitle('Product | Onesa AI Robot');await expect(page.getByRole('heading',{name:/Explore motion/})).toBeVisible();await expect(page.getByRole('img',{name:'Illustrated synthetic single-joint simulator'})).toBeVisible();await expect(page.locator('#operator')).toHaveCount(0);expect(privateRequests).toEqual([]);
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBeTruthy();expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21a','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
 if(process.env.ONESA_VISUAL_EVIDENCE_DIR&&[390,1440].includes(width))await page.screenshot({path:`${process.env.ONESA_VISUAL_EVIDENCE_DIR}/${test.info().project.name}/robot-product-${mode}-${width}.png`,fullPage:true});
});
test('system preference change preserves a proposal draft, focus and simulation authority',async({page})=>{
 await page.emulateMedia({colorScheme:'light'});await page.goto('/console');
 await page.getByLabel('Operator name').fill(process.env.ROBOT_TEST_OPERATOR || 'operator');await page.getByLabel('Password',{exact:true}).fill(process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only');await page.getByRole('button',{name:'Sign in',exact:true}).click();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByLabel('Confirm password to reset').fill(process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only');await page.getByRole('button',{name:'Reset simulation stop'}).click();await expect(page.locator('#stop-state')).toContainText('Ready');
 const target=page.getByLabel('Target position');await target.fill('0.08');await target.focus();await page.emulateMedia({colorScheme:'dark'});await expect(target).toHaveValue('0.08');await expect(target).toBeFocused();await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
 await page.getByRole('button',{name:'Create proposal'}).click();await expect(page.locator('#proposed-id')).toContainText(/[a-f0-9-]{36}/);const taskId=await page.locator('#proposed-id').textContent();await page.getByLabel('Confirm operator password',{exact:true}).fill(process.env.ROBOT_TEST_PASSWORD || 'browser-test-operator-only');await page.getByRole('button',{name:'Approve simulation task'}).click();await expect(page.locator('#notice')).toContainText('Simulation running');
 const mutations=[];page.on('request',request=>{if(request.method()==='POST'&&!request.url().endsWith('/heartbeat'))mutations.push(new URL(request.url()).pathname);});await page.emulateMedia({colorScheme:'light'});await expect(page.locator('#history li').filter({hasText:taskId})).toContainText('completed',{timeout:6000});expect(mutations).toEqual([]);await expect(page.getByRole('button',{name:'Sign out'})).toBeVisible();
});
test('forced colors and reduced motion keep operator navigation and focus accessible',async({page})=>{
 await page.emulateMedia({forcedColors:'active',reducedMotion:'reduce',colorScheme:'dark'});await page.goto('/console');await page.keyboard.press('Tab');await expect(page.getByRole('link',{name:'Skip to content'})).toBeFocused();await expect(page.getByLabel('Operator name')).toBeVisible();expect(await page.evaluate(()=>getComputedStyle(document.querySelector('.skip')).outlineStyle)).not.toBe('none');
});
