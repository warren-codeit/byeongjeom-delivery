// 헤드리스 크롬으로 게임을 실제 구동해 결과·스크린샷을 남긴다 (CDP, 외부 의존 없음).
// 사용: node tools/headless-run.mjs <url> <초> <out.png> [state]
//   state 를 주면 마지막에 G(상태)를 JSON으로 출력한다.
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
const [url, secs = '5', out = 'shot.png', wantState] = process.argv.slice(2);
const CHROME = process.env.CHROME || '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const port = 9222 + Math.floor(Math.random() * 500);
const chrome = spawn(CHROME, ['--headless=new', '--disable-gpu', '--hide-scrollbars', '--mute-audio', `--remote-debugging-port=${port}`, '--window-size=390,844', '--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--force-device-scale-factor=2', '--user-data-dir=/tmp/bj-chrome-' + port, 'about:blank'], { stdio: 'ignore' });
const sleep = ms => new Promise(r => setTimeout(r, ms));
let ws, id = 0; const pending = new Map();
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
try {
  let targets;
  for (let i = 0; i < 40; i++){ try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); if (targets.length) break; } catch (e) {} await sleep(250); }
  const page = targets.find(t => t.type === 'page');
  ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise(r => ws.onopen = r);
  const errors = [];
  ws.onmessage = e => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)){ const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(JSON.stringify(m.error))) : p.res(m.result); } else if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text + ' ' + (m.params.exceptionDetails.exception?.description || '')); else if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') errors.push(m.params.args.map(a => a.value || a.description).join(' ')); };
  await send('Runtime.enable'); await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: 390, height: 844, deviceScaleFactor: 2, mobile: true });
  await send('Page.navigate', { url });
  await sleep(+secs * 1000);
  const shot = await send('Page.captureScreenshot', { format: 'png' });
  writeFileSync(out, Buffer.from(shot.data, 'base64'));
  if (wantState && wantState.startsWith('eval:')){ const r = await send('Runtime.evaluate', { expression: wantState.slice(5), returnByValue: true, awaitPromise: true }); console.log(JSON.stringify(r.result.value ?? r.result.description ?? r)); }
  else if (wantState){ const r = await send('Runtime.evaluate', { expression: 'JSON.stringify({scene:G.scene,t:G.t,timeLeft:G.timeLeft,s:G.s,v:G.v,soup:G.soup,bag:G.bag,score:G.score,result:G.result,objs:G.objs.length,route_m:getRouteLen()})', returnByValue: true }); console.log(r.result.value); }
  console.log(JSON.stringify({ errors }));
} finally { chrome.kill('SIGKILL'); }
