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
for (const route of ['/api/status', '/api/rule', '/api/carrier', '/api/learn', '/api/send', '/api/calibration']) {
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
assert.ok(html.includes('.modal section{box-sizing:border-box;width:100%;max-width:340px;max-height:100%;overflow-y:auto'));
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
let learnState = 0;
let learned = false;
let sendError = 0;
let rising = false;
let failAction = '';
let errorBody = '操作失败';
let failureStatus = 503;
let networkFailure = false;
let clickTime = 10000;
let calibrationRelease = null;
let holdCalibration = false;
const requests = [];
// 用最小 DOM、fetch 和定时器 mock 执行实际脚本，不访问设备或启动真实轮询。
async function loadPage() {
  const elements = new Map();
  const intervals = [];
  let statusReads = 0;
  const context = {
    console: {debug() {}},
    Date: {now() { return clickTime; }},
    document: {getElementById(id) {
      if (!elements.has(id)) elements.set(id, {value: '', disabled: false, textContent: '', innerHTML: '',
        hidden: id === 'calModal', focus() { this.focused = true; }});
      return elements.get(id);
    }},
    setInterval(callback, delay) { intervals.push({callback, delay}); },
    async fetch(path, options) {
      if (networkFailure) throw new Error('网络中断');
      if (path === '/api/status') {
        statusReads++;
        assert.strictEqual(options.cache, 'no-store');
        return {ok: !failStatus, json: async () => ({
          valid, temperature10, sensorError: 7, carrier: storedCarrier, learnState, learnError: 9,
          batteryMv, batteryValid, batteryError: 8,
          rules: [0, 1].map(() => ({threshold10: 220, rising,
            enabled: false, learned, sendError}))
        })};
      }
      const data = JSON.parse(options.body);
      requests.push({path, data});
      if (path === '/api/calibration' && holdCalibration)
        await new Promise(resolve => { calibrationRelease = resolve; });
      if (path === failAction)
        return {ok: false, status: failureStatus, json: async () => ({error: errorBody})};
      if (path === '/api/carrier' && failSave)
        return {ok: false, json: async () => ({error: 'save failed'})};
      if (path === '/api/carrier') storedCarrier = data.carrier;
      if (path === '/api/learn') learnState = 1;
      if (path === '/api/calibration') {
        if (data.type === 'temperature') temperature10 = data.reference10;
        else batteryMv = data.referenceMv;
      }
      return {ok: true, json: async () => ({ok: true})};
    }
  };
  vm.createContext(context);
  vm.runInContext(script[1], context, {filename: 'thermostat-page.js'});
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
  assert.strictEqual(elements.get('learn1').textContent, '学习中···');
  assert.strictEqual(elements.get('learn1').disabled, true);
  assert.strictEqual(elements.get('learn2').textContent, '学习红外');
  assert.strictEqual(elements.get('learn2').disabled, true);
  const learnRequests = requests.length;
  await vm.runInContext('learn(2)', context);
  assert.strictEqual(requests.length, learnRequests);
  learnState = 2; await refresh();
  assert.strictEqual(elements.get('learn1').textContent, '学习中···');
  learnState = 3; await refresh();
  assert.strictEqual(elements.get('learn1').textContent, '学习红外');
  assert.strictEqual(elements.get('learn1').disabled, false);
  await vm.runInContext('learn(2)', context);
  assert.strictEqual(elements.get('learn2').textContent, '学习中···');
  learnState = 4; await refresh();
  assert.strictEqual(elements.get('learn2').textContent, '学习红外');
  assert.strictEqual(elements.get('learn2').disabled, false);
  learnState = 0; await refresh();
  elements.get('t1').value = '-10';
  elements.get('d1').value = '1';
  elements.get('e1').checked = true;
  await vm.runInContext('save(1)', context);
  assert.strictEqual(requests.at(-1).path, '/api/rule');
  assert.deepStrictEqual(requests.at(-1).data, {slot: 1, threshold10: -100, rising: true, enabled: true});
  for (const value of ['', '   ', 'invalid', 'Infinity']) {
    const before = requests.length;
    elements.get('t1').value = value;
    await vm.runInContext('save(1)', context);
    assert.strictEqual(elements.get('message').textContent, '请输入温度');
    assert.strictEqual(requests.length, before);
  }
  elements.get('t1').value = '50';
  elements.get('d1').value = '0';
  elements.get('e1').checked = false;
  await vm.runInContext('save(1)', context);
  assert.deepStrictEqual(requests.at(-1).data, {slot: 1, threshold10: 500, rising: false, enabled: false});
  await vm.runInContext('send(2)', context);
  assert.strictEqual(requests.at(-1).path, '/api/send');
  assert.strictEqual(requests.at(-1).data.slot, 2);
  assert.strictEqual(elements.get('message').textContent, '已发送第2组红外码');
  for (const [path, call] of [['/api/rule', 'save(1)'], ['/api/learn', 'learn(1)'], ['/api/send', 'send(1)']]) {
    failAction = path;
    await vm.runInContext(call, context);
    assert.strictEqual(elements.get('message').textContent, '操作失败');
    if (path === '/api/learn') {
      assert.strictEqual(elements.get('learn1').textContent, '学习红外');
      assert.strictEqual(elements.get('learn1').disabled, false);
      assert.strictEqual(elements.get('learn2').disabled, false);
    }
  }
  errorBody = '';
  await vm.runInContext('send(1)', context);
  assert.strictEqual(elements.get('message').textContent, 'HTTP 503');
  failAction = '';
  learned = true;
  sendError = 6;
  for (const state of [3, 4, 0]) {
    learnState = state;
    await refresh();
    if (state === 3) assert.strictEqual(elements.get('message').textContent, '红外学习成功并已保存');
    if (state === 4) assert.strictEqual(elements.get('message').textContent, '红外学习失败，错误码 9');
  }
  assert.strictEqual(elements.get('info1').textContent, '已学习；上次发送错误码 6');
  const modal = context.document.getElementById('calModal');
  const input = context.document.getElementById('calValue');
  const submit = () => vm.runInContext('submitCalibration({preventDefault(){}})', context);
  const tap = (i, count = 5) => {
    for (let n = 0; n < count; n++) {
      vm.runInContext(`calibrationTap(${i})`, context); clickTime += 100;
    }
  };
  tap(1, 4); tap(2, 1);
  assert.strictEqual(modal.hidden, true); // 两个标题互不累计。
  tap(1, 1);
  assert.strictEqual(modal.hidden, false);
  assert.strictEqual(elements.get('calTitle').textContent, '温度校正');
  assert.strictEqual(input.step, '0.1');
  let beforeCal = requests.length;
  vm.runInContext('closeCalibration()', context);
  assert.strictEqual(modal.hidden, false); // 弹出后的惯性点击不能取消或提交。
  assert.strictEqual(input.focused, undefined); // 不自动弹键盘改变位置。
  input.value = '25.5'; await submit();
  assert.strictEqual(requests.length, beforeCal);
  clickTime += 699; vm.runInContext('closeCalibration()', context);
  assert.strictEqual(modal.hidden, false);
  clickTime += 1; vm.runInContext('closeCalibration()', context);
  assert.strictEqual(modal.hidden, true);
  assert.strictEqual(requests.length, beforeCal);
  tap(1, 4); clickTime += 3001; tap(1, 1);
  assert.strictEqual(modal.hidden, true);
  tap(1, 4);
  assert.strictEqual(modal.hidden, false);
  clickTime += 800;
  for (const value of ['', 'NaN', 'Infinity', '-10.1', '50.1', '25.55']) {
    input.value = value; await submit();
    assert.strictEqual(requests.length, beforeCal);
    assert.strictEqual(modal.hidden, false);
  }
  input.value = '25.5';
  await submit();
  assert.deepStrictEqual(requests.at(-1).data, {type: 'temperature', reference10: 255});
  assert.strictEqual(modal.hidden, true);
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 25.5 °C');
  tap(2);
  assert.strictEqual(elements.get('calTitle').textContent, '电池电压校正');
  assert.strictEqual(input.step, '0.001');
  clickTime += 800;
  beforeCal = requests.length;
  for (const value of ['2.499', '4.501', '3.5951', '']) {
    input.value = value; await submit(); assert.strictEqual(requests.length, beforeCal);
  }
  input.value = '3.595'; failAction = '/api/calibration'; errorBody = 'ESP_ERR_INVALID_STATE'; failureStatus = 409;
  await submit();
  assert.strictEqual(modal.hidden, false);
  assert.strictEqual(input.value, '3.595');
  assert.match(elements.get('calError').textContent, /读数不可用或已过期/);
  assert.strictEqual(elements.get('calSave').disabled, false);
  failureStatus = 400; await submit();
  assert.match(elements.get('calError').textContent, /超出允许范围/);
  failureStatus = 500; await submit();
  assert.match(elements.get('calError').textContent, /保存失败/);
  failureStatus = 503;
  failAction = ''; networkFailure = true;
  await submit();
  assert.match(elements.get('calError').textContent, /网络中断/);
  networkFailure = false; holdCalibration = true;
  const saving = submit();
  assert.strictEqual(elements.get('calSave').disabled, true);
  assert.strictEqual(elements.get('calCancel').disabled, true);
  assert.strictEqual(input.disabled, true);
  beforeCal = requests.length;
  await submit(); vm.runInContext('closeCalibration()', context); tap(1);
  assert.strictEqual(requests.length, beforeCal);
  assert.strictEqual(modal.hidden, false);
  holdCalibration = false; calibrationRelease(); await saving;
  assert.deepStrictEqual(requests.at(-1).data, {type: 'battery', referenceMv: 3595});
  assert.strictEqual(modal.hidden, true);
  assert.strictEqual(elements.get('battery').textContent, '电池电压 3.60 V');
  valid = false; await refresh(); tap(1);
  assert.strictEqual(modal.hidden, true);
  valid = true; batteryValid = false; await refresh(); tap(2);
  assert.strictEqual(modal.hidden, true);
  batteryValid = true; await refresh();
  networkFailure = true;
  await refresh();
  assert.strictEqual(elements.get('message').textContent, '网络中断');
  await vm.runInContext('saveCarrier()', context);
  assert.match(elements.get('message').textContent, /网络中断/);
  networkFailure = false;
  rising = true;
  ({elements} = await loadPage());
  assert.strictEqual(elements.get('carrier').value, '36');
  assert.strictEqual(elements.get('d1').value, '1');
  learnState = 1;
  ({elements, refresh} = await loadPage());
  for (const i of [1, 2]) {
    assert.strictEqual(elements.get('learn'+i).textContent, '学习中···');
    assert.strictEqual(elements.get('learn'+i).disabled, true);
  }
  learnState = 4; await refresh();
  assert.strictEqual(elements.get('learn1').textContent, '学习红外');
  assert.strictEqual(elements.get('learn2').disabled, false);
  // 学习前的旧成功/失败响应都不能覆盖已接受的学习状态。
  ({context, elements, refresh} = await loadPage());
  const fetchStatus = () => context.fetch('/api/status', {cache: 'no-store'});
  function delayStatus(start = true) {
    const fetch = context.fetch;
    let resolve, reject, requested;
    const ready = new Promise(done => { requested = done; });
    context.fetch = (path, options) => {
      if (path !== '/api/status') return fetch(path, options);
      context.fetch = fetch;
      requested();
      return new Promise((done, fail) => { resolve = done; reject = fail; });
    };
    const pending = start ? refresh() : null;
    return {pending, ready, resolve(value) { resolve(value); }, reject(error) { reject(error); }};
  }
  for (const failure of [false, true]) {
    learnState = 0; await refresh();
    const snapshot = await (await fetchStatus()).json();
    const stale = delayStatus();
    await vm.runInContext('learn(1)', context);
    const message = elements.get('message').textContent;
    if (failure) stale.reject(Error('旧请求网络中断'));
    else stale.resolve({ok: true, json: async () => snapshot});
    await stale.pending;
    assert.strictEqual(elements.get('learn1').textContent, '学习中···');
    assert.strictEqual(elements.get('learn1').disabled, true);
    assert.strictEqual(elements.get('learn2').disabled, true);
    assert.strictEqual(elements.get('message').textContent, message);
    assert.strictEqual(vm.runInContext('latestStatus.learnState', context), 1);
    const before = requests.length;
    await vm.runInContext('learn(2)', context);
    assert.strictEqual(requests.length, before);
  }
  // 学习已接受但确认状态尚未返回时，也不能再次点击学习。
  learnState = 0; await refresh();
  const confirming = delayStatus(false);
  const learning = vm.runInContext('learn(1)', context);
  await confirming.ready;
  const before = requests.length;
  await vm.runInContext('learn(2)', context);
  assert.strictEqual(requests.length, before);
  const state = await (await fetchStatus()).json();
  confirming.resolve({ok: true, json: async () => state});
  await learning;
  // POST 等待期间发出的轮询，也必须在学习接受后失效。
  learnState = 0; await refresh();
  const beforeLearn = await (await fetchStatus()).json();
  const fetch = context.fetch;
  let accept;
  context.fetch = async (path, options) => {
    if (path === '/api/learn') await new Promise(done => { accept = done; });
    return fetch(path, options);
  };
  const accepting = vm.runInContext('learn(1)', context);
  const during = delayStatus();
  accept(); await accepting;
  during.resolve({ok: true, json: async () => beforeLearn}); await during.pending;
  assert.strictEqual(elements.get('learn1').disabled, true);
  assert.strictEqual(vm.runInContext('latestStatus.learnState', context), 1);
  context.fetch = fetch;
  // 普通轮询乱序时保留较新状态；较新请求未完成不阻止有效旧请求更新。
  learnState = 0; await refresh();
  const snapshot = await (await fetchStatus()).json();
  const stale = delayStatus();
  temperature10 = 271; await refresh();
  stale.resolve({ok: true, json: async () => snapshot});
  await stale.pending;
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 27.1 °C');
  const older = delayStatus();
  const newer = delayStatus();
  older.resolve({ok: true, json: async () => snapshot}); await older.pending;
  assert.strictEqual(elements.get('temperature').textContent, '当前温度 '+(snapshot.temperature10/10).toFixed(1)+' °C');
  newer.resolve({ok: true, json: async () => state}); await newer.pending;
  learnState = 3; await refresh();
  assert.strictEqual(elements.get('learn1').disabled, false);
  assert.strictEqual(elements.get('message').textContent, '红外学习成功并已保存');
  console.log('control page: stale status success/errors, learning confirmation and out-of-order polling passed');
  console.log('control page: five taps, calibration dialogs/precision/save/cancel/errors, routes, battery and shared carrier passed');
}
check().catch(error => { console.error(error); process.exitCode = 1; });
