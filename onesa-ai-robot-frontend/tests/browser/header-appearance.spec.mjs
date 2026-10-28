import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('header contrast follows system preference without changing sign-in entries or focus',async({page})=>{
 const errors=[];page.on('pageerror',error=>errors.push(error.name));
 await page.emulateMedia({colorScheme:'dark',reducedMotion:'reduce'});
 await page.goto('/console');await expect(page.locator('#login-form')).toBeVisible();
 await page.locator('#name').fill('synthetic-appearance-only');
 await page.locator('#password').fill('synthetic-not-an-account-password');
 await page.locator('#password').focus();
 const mutations=[];page.on('request',request=>{if(!['GET','HEAD'].includes(request.method()))mutations.push(new URL(request.url()).pathname);});
 for(const width of [390,1440,320]){
  await page.setViewportSize({width,height:900});
  for(const mode of ['light','dark','light','dark']){
   await page.emulateMedia({colorScheme:mode});
   const text=mode==='light'?'rgb(16, 38, 62)':'rgb(229, 237, 246)';
   const canvas=mode==='light'?'rgb(255, 255, 255)':'rgb(11, 21, 35)';
   await expect(page.locator('body')).toHaveCSS('color',text);
   await expect(page.locator('header')).toHaveCSS('background-color',canvas);
   for(const target of ['header .wordmark','header .wordmark span','header nav a[href="/"]'])await expect(page.locator(target)).toHaveCSS('color',text);
   await expect(page.locator('#name')).toHaveValue('synthetic-appearance-only');
   await expect(page.locator('#password')).toHaveValue('synthetic-not-an-account-password');
   await expect(page.locator('#password')).toBeFocused();
   expect((await new AxeBuilder({page}).include('header').withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
  }
 }
 expect(mutations).toEqual([]);
 expect(errors).toEqual([]);
});
