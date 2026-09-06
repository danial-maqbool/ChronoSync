import {test,expect} from '@playwright/test';
import fs from 'node:fs';

test('real browser workflow and responsive workspace',async({page,request})=>{
 const errors:string[]=[],assets:string[]=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('response',r=>{if(r.status()>=400&&(/\/assets\/|favicon/.test(r.url())))assets.push(r.url())});
 await request.post('/api/demo');
 const ws=await (await request.get('/api/workspace')).json();
 for(const e of ws.events.filter((e:any)=>e.status==='PROPOSED'&&!e.resolution.warnings.length).slice(0,6))await request.post('/api/events/'+e.id+'/action',{data:{action:'approve'}});
 fs.mkdirSync('../docs/screenshots',{recursive:true});
 await page.goto('/');await expect(page.getByRole('heading',{name:'A clearer view of what’s next.'})).toBeVisible();
 await page.screenshot({path:'../docs/screenshots/dashboard.png',fullPage:true});
 for(const [nav,file] of [['Event Inbox','event_inbox'],['Upcoming','upcoming'],['Calendar','calendar'],['Sources','sources'],['Tags','tags'],['Rules','rules'],['Completed','completed'],['Audit History','audit'],['Settings','settings']]){
  await page.locator('nav').getByRole('button',{name:nav,exact:true}).click();
  await expect(page.locator('h1')).toBeVisible();
  await page.screenshot({path:`../docs/screenshots/${file}.png`,fullPage:true});
 }
 await page.getByRole('button',{name:'Quick capture',exact:true}).click();
 const dialog=page.getByRole('dialog');
 await dialog.getByLabel('Source name').fill('Browser acceptance');
 await dialog.getByLabel('Message',{exact:true}).fill('Browser acceptance meeting on October 20 2026 at 4 PM.');
 await dialog.getByLabel('Source date & time (optional)').fill('2026-09-03T10:00');
 await dialog.getByRole('button',{name:'Find events',exact:true}).click();
 await expect(dialog).not.toBeVisible();
 await page.getByRole('button',{name:/Browser acceptance meeting/}).click();
 await expect(page.getByRole('heading',{name:'Source evidence',exact:true})).toBeVisible();
 await page.screenshot({path:'../docs/screenshots/event_detail.png',fullPage:true});
 await page.screenshot({path:'../docs/screenshots/source_evidence.png',fullPage:true});
 await page.screenshot({path:'../docs/screenshots/date_resolution.png',fullPage:true});
 await page.getByRole('button',{name:'Approve',exact:true}).click();
 await expect(page.getByRole('status')).toContainText('Event updated');
 await page.locator('nav').getByRole('button',{name:'Upcoming',exact:true}).click();
 await page.getByRole('button',{name:/Browser acceptance meeting/}).click();
 await page.getByRole('button',{name:'Sync approved event',exact:true}).click();
 await expect(page.locator('.detail-content')).toContainText('SYNCED');
 await page.getByRole('button',{name:'Edit',exact:true}).click();
 await page.getByRole('dialog').getByLabel('Event title').fill('Browser verified meeting');
 await page.getByRole('dialog').getByRole('button',{name:'Save event'}).click();
 await expect(page.getByRole('dialog')).not.toBeVisible();
 await expect(page.getByRole('heading',{name:'Browser verified meeting',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Complete',exact:true}).click();
 await page.getByRole('button',{name:'Close event details'}).click();
 await page.locator('nav').getByRole('button',{name:'Completed',exact:true}).click();
 await expect(page.getByRole('button',{name:/Browser verified meeting/})).toBeVisible();
 await page.locator('nav').getByRole('button',{name:'Dashboard',exact:true}).click();
 for(const [width,height] of [[1920,1080],[1440,900],[1366,768],[1024,768],[390,844]]){
  await page.setViewportSize({width,height});
  await expect(page.locator('h1')).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  await page.screenshot({path:`../docs/screenshots/responsive-${width}.png`,fullPage:true});
 }
 await page.getByRole('button',{name:'Toggle navigation'}).click();
 await page.locator('nav').getByRole('button',{name:'Event Inbox',exact:true}).click();
 expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
 await page.screenshot({path:'../docs/screenshots/mobile-inbox.png',fullPage:true});
 expect(errors).toEqual([]);expect(assets).toEqual([]);
});
