import {test,expect} from '@playwright/test';

for(const route of ['/','/privacy'])for(const colorScheme of ['light','dark'])test(`public ${route} ${colorScheme} reflows enlarged text without horizontal scrolling`,async({page})=>{
 let privateRequests=0;page.on('request',request=>{if(new URL(request.url()).pathname.startsWith('/api/v1/'))privateRequests++;});
 await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
 for(const width of [320,390]){
  await page.setViewportSize({width,height:844});
  await page.goto(route);
  await expect(page.locator('main h1')).toBeVisible();
  const scriptClasses=await page.locator('script[src]').evaluateAll(nodes=>nodes.slice(0,8).map(node=>{
   try{
    const url=new URL(node.src);
    if(!['http:','https:'].includes(url.protocol))return 'NON_HTTP_SCRIPT';
    if(url.origin===location.origin)return url.pathname.startsWith('/.well-known/vercel/security/')?'PROVIDER_SECURITY_SCRIPT':'OWN_ORIGIN_SCRIPT';
    return url.hostname==='vercel.live'?'PROVIDER_TOOLBAR_SCRIPT':'OTHER_EXTERNAL_SCRIPT';
   }catch{return 'MALFORMED_SCRIPT_SOURCE';}
  }));
  await expect(page.locator('script[src]'),`Public routes must remain script-free; observed classes: ${JSON.stringify(scriptClasses)}`).toHaveCount(0);
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
