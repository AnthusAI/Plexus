// Shim for next/config only when the package no longer ships it (some canary builds).
// Avoid clobbering the real Next.js implementation when it exists.
const fs = require('fs');
const path = require('path');
const target = path.join(__dirname, '..', 'node_modules', 'next', 'config.js');
const content = 'module.exports = { default: () => null, setConfig: () => {} };\n';
try {
  fs.writeFileSync(target, content, { flag: 'wx' });
} catch (error) {
  if (!error || error.code !== 'EEXIST') {
    throw error;
  }
}
