const fs = require('fs');
const path = require('path');

// 1. Patch fetch.js to use undici.fetch for Node 26 compatibility with undici.Agent
const fetchJsPath = path.join(__dirname, '..', 'node_modules', '@expo', 'cli', 'build', 'src', 'utils', 'fetch.js');
if (fs.existsSync(fetchJsPath)) {
  let content = fs.readFileSync(fetchJsPath, 'utf8');
  if (content.includes('typeof globalThis.fetch !== "undefined"')) {
    content = content.replace(
      'const fetch = typeof globalThis.fetch !== "undefined" ? globalThis.fetch : require("undici").fetch;',
      'const fetch = require("undici").fetch;'
    ).replace(
      'const Headers = typeof globalThis.Headers !== "undefined" ? globalThis.Headers : require("undici").Headers;',
      'const Headers = require("undici").Headers;'
    );
    fs.writeFileSync(fetchJsPath, content, 'utf8');
    console.log('[patch-expo-node26] Patched fetch.js for Node 26 Undici dispatcher compatibility.');
  }
}

// 2. Patch downloadExpoGoAsync.js to check local cache before re-downloading
const dlPath = path.join(__dirname, '..', 'node_modules', '@expo', 'cli', 'build', 'src', 'utils', 'downloadExpoGoAsync.js');
if (fs.existsSync(dlPath)) {
  let content = fs.readFileSync(dlPath, 'utf8');
  if (!content.includes('fs.existsSync(outputPath)')) {
    content = content.replace(
      'const outputPath = getFilePath(filename);\n        debug(`Downloading Expo Go from "${url}" to "${outputPath}".`);',
      'const outputPath = getFilePath(filename);\n        const fs = require("fs");\n        if (fs.existsSync(outputPath) && fs.statSync(outputPath).size > 10000000) {\n            debug(`Expo Go already cached at "${outputPath}".`);\n            return outputPath;\n        }\n        debug(`Downloading Expo Go from "${url}" to "${outputPath}".`);'
    );
    fs.writeFileSync(dlPath, content, 'utf8');
    console.log('[patch-expo-node26] Patched downloadExpoGoAsync.js with local cache check.');
  }
}
