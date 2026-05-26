// Copies manifest.json + icons into dist/ after Vite build (Chrome only)
import { readFileSync, writeFileSync, cpSync, mkdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');
const distDir = resolve(root, 'dist');

if (!existsSync(distDir)) mkdirSync(distDir, { recursive: true });

const manifest = JSON.parse(
  readFileSync(resolve(root, 'manifests', 'chrome.json'), 'utf8')
);
writeFileSync(resolve(distDir, 'manifest.json'), JSON.stringify(manifest, null, 2));

const iconsSrc = resolve(root, 'icons');
const iconsDst = resolve(distDir, 'icons');
if (existsSync(iconsSrc)) cpSync(iconsSrc, iconsDst, { recursive: true });

console.log('✓ Chrome manifest + icons copied to dist/');
