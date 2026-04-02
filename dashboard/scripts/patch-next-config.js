// Shim for next/config removed in Next.js 15.6.0-canary+
// @storybook/nextjs@8.x requires next/config at startup; this stub satisfies it.
const fs = require('fs');
const path = require('path');
const target = path.join(__dirname, '..', 'node_modules', 'next', 'config.js');
const content = 'module.exports = { default: () => null, setConfig: () => {} };\n';
fs.writeFileSync(target, content);
