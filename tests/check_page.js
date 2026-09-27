const fs = require('fs');
const source = fs.readFileSync('main/page.h', 'utf8');
const lines = source.split(/\r?\n/).filter(line => line.startsWith('"'));
const html = lines.map(line => JSON.parse(line.replace(/;$/, ''))).join('');
const script = html.match(/<script>([\s\S]*)<\/script>/);
if (!script) throw new Error('page script missing');
new Function(script[1]);
for (const route of ['/api/status', '/api/rule', '/api/learn', '/api/send']) {
  if (!html.includes(route)) throw new Error(`${route} missing`);
}
console.log('control page: script syntax and routes passed');
