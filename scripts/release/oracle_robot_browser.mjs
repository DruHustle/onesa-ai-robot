// The owner commissions these exact bytes separately from application candidates.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { chromium, firefox, webkit, expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
export async function checkUI(request,directory,engines={chromium,firefox,webkit}){
let errors=0,replayRequests=0,violations=0;
const results=[];
const outcomes={normal:'Completed · normal readings',threshold:'Completed · findings to review',discrepancy:'Completed · findings to review',missing:'Completed · findings to review',stale:'Completed · findings to review',units:'Completed · findings to review',interrupted:'Interrupted · not completed'};
const write=(name,value)=>fs.writeFileSync(directory+'/'+name,JSON.stringify(value),{flag:'wx',mode:0o600});
for(const [engine,type] of Object.entries(engines)){
 const browser=await type.launch({headless:true});
 try{
  const context=await browser.newContext({viewport:{width:390,height:844},colorScheme:'dark',reducedMotion:'reduce',extraHTTPHeaders:request.provider.bypass?{'x-vercel-protection-bypass':request.provider.bypass}:{}});
  const page=await context.newPage();
  page.on('pageerror',()=>errors++);
  const publicResponses=[];
  page.on('request',req=>{if(new URL(req.url()).pathname.startsWith('/api/'))publicResponses.push(req.url());});
  await page.goto(request.origin+'/');
  await expect(page.getByRole('heading',{level:1})).toBeVisible();
  assert.equal(await page.locator('script').count(),0);
  assert.equal(publicResponses.length,0);
  await page.screenshot({path:directory+'/'+engine+'-public.png',fullPage:true});
  await page.goto(request.origin+'/console');
  await expect(page.locator('#login-form')).toBeVisible();
  const anon=await page.request.get(request.origin+'/api/v1/missions');assert.equal(anon.status(),401);
  await page.locator('#name').fill(request.credentials.operator);
  await page.locator('#password').fill(request.credentials.password);
  await page.getByRole('button',{name:'Sign in',exact:true}).click();
  await expect(page.locator('#operator')).toBeVisible({timeout:25000});
  if(request.read_only && request.binding.component==='frontend'){
   await expect(page.locator('#mission-form')).toBeVisible();
   await expect(page.locator('#mission-scenario option')).toHaveCount(7);
   await expect(page.locator('#mission-readiness')).toContainText('Stopped');
   await expect(page.locator('#mission-submit')).toBeDisabled();
  }
  const scenarios=request.read_only?[]:Object.keys(outcomes);
  for(const scenario of scenarios){
   // Preflight has already refused unknown active work. Stop/reset here belong
   // only to this bounded staging fixture's own session and completed runs.
   await page.locator('#stop').click();
   await expect(page.locator('#reset-form')).toBeVisible();
   await page.locator('#reset-password').fill(request.credentials.password);
   await page.locator('#reset-submit').click();
   await expect(page.locator('#mission-submit')).toBeEnabled();
   await page.locator('#mission-scenario').selectOption(scenario);
   await page.locator('#mission-submit').click();
   await expect(page.locator('#mission-steps li')).toHaveCount(5);
   await page.locator('#mission-password').fill(request.credentials.password);
   await page.locator('#mission-approve-submit').click();
   await expect(page.locator('#mission-outcome')).toHaveText(outcomes[scenario],{timeout:20000});
   const mutations=[];
   const watch=req=>{if(req.method()!=='GET'&&!req.url().endsWith('/heartbeat'))mutations.push(new URL(req.url()).pathname);};
   page.on('request',watch);
   await page.locator('#replay-time').fill('0');await page.locator('#replay-time').fill('3');
   const downloadPromise=page.waitForEvent('download');await page.locator('#mission-export').click();
   const download=await downloadPromise;
   const stream=await download.createReadStream();const chunks=[];for await(const chunk of stream)chunks.push(chunk);
   const raw=Buffer.concat(chunks);assert(raw.length<=32768);const detail=JSON.parse(raw.toString('utf8'));
   assert.equal(detail.record.plan.scenario,scenario);
   assert.equal(detail.record.plan.asset.id,'pump-p-101');
   assert.equal(detail.record.plan.physical_actuation,false);
   page.off('request',watch);replayRequests+=mutations.length;assert.equal(mutations.length,0);
   write(engine+'-'+scenario+'-inspection.json',detail);
   results.push({engine,scenario,mission_id:detail.id,outcome:detail.record.outcome,export_sha256:createHash('sha256').update(raw).digest('hex')});
  }
  for(const [width,mode] of [[390,'dark'],[1440,'light'],[320,'light']]){
   await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme:mode});
   if(!request.read_only){await page.locator('#replay-time').focus();await page.keyboard.press('Home');await expect(page.locator('#replay-time')).toBeFocused();}
   await page.emulateMedia({colorScheme:mode==='dark'?'light':'dark'});
   await expect.poll(()=>page.evaluate(()=>getComputedStyle(document.body).color)).toBe(mode==='dark'?'rgb(16, 38, 62)':'rgb(229, 237, 246)');
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   const audit=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze();
   violations+=audit.violations.length;
   if(audit.violations.length)write(engine+'-'+width+'-axe.json',audit.violations);
   assert.equal(audit.violations.length,0);
  }
  await page.screenshot({path:directory+'/'+engine+'-operator.png',fullPage:true});
  await page.locator('#logout').click();
  await expect(page.locator('#login-form')).toBeVisible();
  if(request.environment==='staging'||request.binding.component==='frontend')await expect(page.locator('#mission-readings')).toBeEmpty();
  assert.equal((await page.request.get(request.origin+'/api/v1/missions')).status(),401);
  await context.close();
 }finally{await browser.close();}
}
assert.equal(errors,0);assert.equal(replayRequests,0);assert.equal(violations,0);
const receipt={status:'PASS',binding:request.binding,environment:request.environment,engines:Object.keys(engines),results,replay_operational_requests:replayRequests,javascript_errors:errors,accessibility_violations:violations,production_operational_mutations:0,observed_at:new Date().toISOString()};
write('browser-receipt.json',receipt);return receipt;
}

if(process.argv[1] && import.meta.url===new URL('file:'+process.argv[1]).href){
const request=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
assert.equal(request.binding.repository,'DruHustle/onesa-ai-robot');
assert.equal(request.read_only,request.environment==='production');
assert.match(request.origin,request.environment==='production'?/^https:\/\/robot\.onesa\.eu$/:/^https:\/\/onesa-ai-robot-git-staging-[a-z0-9-]+\.vercel\.app$/);
await checkUI(request,'/private/output');
}
