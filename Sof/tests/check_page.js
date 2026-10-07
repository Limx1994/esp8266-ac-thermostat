const fs = require('fs');
const assert = require('assert');
const vm = require('vm');
// 从 C 字符串还原实际页面，先检查脚本语法和 API 路径，再执行模拟交互。
const source = fs.readFileSync('main/page.h', 'utf8');
const lines = source.split(/\r?\n/).filter(line => line.startsWith('"'));
const html = lines.map(line => JSON.parse(line.replace(/;$/, ''))).join('');
const script = html.match(/<script>([\s\S]*)<\/script>/);
if (!script) throw new Error('page script missing');
new Function(script[1]);
for (const route of ['/api/status', '/api/rule', '/api/carrier', '/api/learn', '/api/send']) {
  if (!html.includes(route)) throw new Error(`${route} missing`);
}
assert.strictEqual((html.match(/<select id='carrier'/g) || []).length, 1);
assert.ok(html.indexOf("id='carrier'") < html.indexOf("id='cards'"));
assert.ok(!html.includes("id='c${i}'"));
assert.ok(html.includes('热点未使用3分钟关闭，使用后空闲10分钟关闭'));
assert.ok(html.includes('S2关闭热点进入休眠，每60秒测温并按规则发送红外'));
assert.ok(!html.includes('S2暂停温控'));
assert.ok(html.includes('休眠中两键都可唤醒，S1开关Wi-Fi热点'));
assert.ok(html.includes("id='lowBattery' role='status' hidden"));
assert.ok(html.includes('热点开启时暂停自动温控，可手动测试红外'));
assert.ok(html.includes('关闭后每60秒采温。首次满足规则即发送'));
assert.ok(html.includes('按温度变化速度调整为2～10分钟间隔'));

let storedCarrier = 40;
let failSave = false;
let temperature10 = 220;
let valid = true;
let failStatus = false;
let batteryMv = 4199;
let batteryValid = true;
const requests = [];
// 用最小 DOM、fetch 和定时器 mock 执行实际脚本，不访问设备或启动真实轮询。
async function loadPage() {
  const elements = new Map();
  const intervals = [];
  let statusReads = 0;
  const context = {
    document: {getElementById(id) {
      if (!elements.has(id)) elements.set(id, {value: '', disabled: false, textContent: '', innerHTML: ''});
      return elements.get(id);
    }},
    setInterval(callback, delay) { intervals.push({callback, delay}); },
    async fetch(path, options) {
      if (path === '/api/status') {
        statusReads++;
        assert.strictEqual(options.cache, 'no-store');
        return {ok: !failStatus, json: async () => ({
          valid, temperature10, sensorError: 7, carrier: storedCarrier, learnState: 0,
          batteryMv, batteryValid, batteryError: 8,
          rules: [0, 1].map(() => ({threshold10: 220, rising: false,
            enabled: false, learned: false, sendError: 0}))
        })};
      }
      const data = JSON.parse(options.body);
      requests.push({path, data});
      if (path === '/api/carrier' && failSave)
        return {ok: false, json: async () => ({error: 'save failed'})};
      if (path === '/api/carrier') storedCarrier = data.carrier;
      return {ok: true, json: async () => ({ok: true})};
    }
  };
  vm.createContext(context);
  vm.runInContext(script[1], context);
  assert.strictEqual(statusReads, 1);
  assert.strictEqual(intervals.length, 1);
  assert.strictEqual(intervals[0].delay, 2000);
  await intervals[0].callback();
  return {context, elements, refresh: intervals[0].callback};
}

async function check() {
  let {context, elements, refresh} = await loadPage();
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 22.0 °C');
  assert.strictEqual(elements.get('battery').textContent, '电池电压 4.20 V');
  assert.strictEqual(elements.get('lowBattery').hidden, true);
  // 验证 3.5 V 边界及读数失败后的提示恢复，防止无效读数触发低电量告警。
  for (const voltage of [3501, 3500, 3499, 3400]) {
    batteryMv = voltage;
    await refresh();
    assert.strictEqual(elements.get('lowBattery').hidden, voltage >= 3500);
  }
  batteryValid = false;
  await refresh();
  assert.strictEqual(elements.get('lowBattery').hidden, true);
  assert.strictEqual(elements.get('battery').textContent, '电池电压读取失败，错误码 8');
  batteryValid = true;
  await refresh();
  assert.strictEqual(elements.get('lowBattery').hidden, false);
  batteryMv = 3780;
  await refresh();
  assert.strictEqual(elements.get('battery').textContent, '电池电压 3.78 V');
  assert.strictEqual(elements.get('lowBattery').hidden, true);
  batteryValid = false;
  await refresh();
  assert.strictEqual(elements.get('battery').textContent, '电池电压读取失败，错误码 8');
  batteryValid = true;
  await refresh();
  assert.strictEqual(elements.get('battery').textContent, '电池电压 3.78 V');
  temperature10 = 235;
  await refresh();
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 23.5 °C');
  valid = false;
  await refresh();
  assert.strictEqual(elements.get('temperature').textContent, '温度读取失败，错误码 7');
  assert.strictEqual(elements.get('battery').textContent, '电池电压 3.78 V');
  valid = true;
  failStatus = true;
  await refresh();
  assert.strictEqual(elements.get('message').textContent, '状态读取失败');
  failStatus = false;
  await refresh();
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 23.5 °C');
  const carrier = elements.get('carrier');
  assert.strictEqual(carrier.value, '40');
  assert.strictEqual(carrier.disabled, false);
  // 保存失败必须恢复已保存频率；成功后重新加载页面仍读取新频率。
  carrier.value = '36';
  failSave = true;
  await vm.runInContext('saveCarrier()', context);
  assert.strictEqual(carrier.value, '40');
  assert.match(elements.get('message').textContent, /频率保存失败/);
  failSave = false;
  carrier.value = '36';
  await vm.runInContext('saveCarrier()', context);
  assert.strictEqual(storedCarrier, 36);
  assert.strictEqual(requests.at(-1).path, '/api/carrier');
  assert.strictEqual(requests.at(-1).data.carrier, 36);
  await vm.runInContext('learn(1)', context);
  assert.strictEqual(requests.at(-1).path, '/api/learn');
  assert.strictEqual(JSON.stringify(requests.at(-1).data), '{"slot":1}');
  ({elements} = await loadPage());
  assert.strictEqual(elements.get('carrier').value, '36');
  console.log('control page: script, routes, 2s refresh, low battery boundary/recovery, errors and shared carrier passed');
}
check().catch(error => { console.error(error); process.exitCode = 1; });
