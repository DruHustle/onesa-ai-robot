import {test,expect} from '@playwright/test';

for(const route of ['/','/privacy'])for(const colorScheme of ['light','dark'])test(`public ${route} ${colorScheme} reflows enlarged text without horizontal scrolling`,async({page})=>{
 let privateRequests=0;page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/v1/'))privateRequests++;});
 await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
 for(const width of [320,390]){
  await page.setViewportSize({width,height:844});
  await page.goto(route);
  await expect(page.locator('main h1')).toBeVisible();
  await expect(page.locator('script[src]')).toHaveCount(0);
  await page.evaluate(async()=>{
   document.documentElement.style.setProperty('font-size','200%','important');
   await document.fonts.ready;
   await new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)));
  });
  expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
  const wordmark=await page.locator('.wordmark').boundingBox();
  expect(wordmark.x+wordmark.width).toBeLessThanOrEqual(width+1);
 }
 expect(privateRequests).toBe(0);
});
