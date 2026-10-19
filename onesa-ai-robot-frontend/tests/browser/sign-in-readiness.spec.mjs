import {test,expect} from '@playwright/test';
import {waitForOperatorSignIn} from './sign-in-acceptance.mjs';

test('sign-in acknowledgement waits for bounded readiness without replaying credentials',async({page})=>{
 let allowReady=false,session=false,logins=0;const mutations=[];
 // Every API request stays in this synthetic fixture, including initial session reads.
 await page.route('**/api/v1/**',async route=>{
  const path=new URL(route.request().url()).pathname;
  let status=200,body={};
  if(path.endsWith('/ready')){status=allowReady?200:503;body=allowReady?{status:'ready',mode:'simulation',physical_actuation:false}:{detail:'Synthetic readiness delay'};}
  else if(path.endsWith('/auth/me')){status=session?200:401;body=session?{csrf:'fixture-csrf'}:{detail:'Synthetic signed out'};}
  else if(path.endsWith('/auth/login')){expect(allowReady).toBe(true);session=true;logins++;body={csrf:'fixture-csrf'};}
  else if(path.endsWith('/auth/logout'))session=false;
  else if(path.endsWith('/status'))body={mode:'simulation',physical_actuation:false,stopped:true,position_radians:0,active_task:null,sampled_at:Date.now()/1000,capabilities:{edge_telemetry:'disconnected'},deployment_environment:'local'};
  else if(path.endsWith('/tasks'))body={tasks:[]};
  if(route.request().method()==='POST'&&!/\/auth\/(?:login|logout)$/.test(path)&&!path.endsWith('/heartbeat'))mutations.push(path);
  await route.fulfill({status,contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto('/console');
 await page.getByLabel('Operator name').fill('synthetic-operator');
 await page.getByLabel('Password',{exact:true}).fill('synthetic-password');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.locator('#notice')).toContainText('Checking simulator readiness');
 // Deliberately exceed the old 5s assertion while staying inside the real 15s readiness bound.
 await page.waitForTimeout(5200);
 expect(logins).toBe(0);await expect(page.getByRole('button',{name:'Sign out'})).toBeHidden();
 allowReady=true;await waitForOperatorSignIn(page);
 expect(logins).toBe(1);expect(mutations).toEqual([]);
 await expect(page.getByLabel('Password',{exact:true})).toHaveValue('');
 await page.getByRole('button',{name:'Sign out'}).click();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
});
