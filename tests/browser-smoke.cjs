// Real Chromium + real local HTTP stack. No routed/mocked API responses or paid calls.
const {chromium}=require('playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_PATH||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
 const page=await browser.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 let assertions=0; const check=(label,ok)=>{if(!ok)throw Error(label);assertions++;console.log('PASS '+label)};
 await page.goto(process.env.STUDIO_TEST_URL||'http://localhost:8080',{waitUntil:'networkidle'});
 check('single heading',await page.getByRole('heading',{level:1}).count()===1);
 const readiness = await (await page.request.get(new URL('/api/config', page.url()).href)).json();
 check('inline readiness retains the backend reason without the old banner',await page.locator('#generation-readiness').isVisible() && (await page.locator('#generation-readiness').textContent()).includes(readiness.blocked_reason || 'Die Bilderstellung ist noch nicht freigegeben.') && await page.getByText('Neue Entwürfe sind derzeit nicht verfügbar.').count()===0);
 check('no placeholder render',await page.locator('img').count()===0);
 check('cost blocked button',await page.getByRole('button',{name:/Meine Konzepte erstellen/}).isDisabled());
 await page.getByRole('radio',{name:'Raumfoto'}).check();
 check('photo upload input',await page.getByLabel(/Dein Raumfoto/).isVisible());
 await page.getByRole('radio',{name:'Grundriss'}).check();
 check('floorplan upload input',await page.getByLabel(/Dein Grundriss/).isVisible());
 await page.getByRole('radio',{name:'Meine Idee'}).check();
 check('text mode upload removed',await page.locator('input[type=file]').count()===0);
 await page.getByRole('button',{name:/Studio fortsetzen/}).click();
 check('secure continuation field',await page.getByLabel('Fortsetzungscode',{exact:true}).getAttribute('type')==='password');
 check('continuation no token in url',!page.url().includes('token'));
 await page.setViewportSize({width:390,height:844});
 check('mobile no horizontal overflow',await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.keyboard.press('Tab');
 check('keyboard focus',await page.evaluate(()=>document.activeElement!==document.body));
 check('zero browser exceptions',errors.length===0);
 console.log(JSON.stringify({assertions,browser:await browser.version(),errors}));
 await browser.close();
})().catch(e=>{console.error(e.message);process.exit(1)});
