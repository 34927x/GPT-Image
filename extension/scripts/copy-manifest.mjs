// Copies the right manifest.json + icons into dist/ after Vite build
import { readFileSync, writeFileSync, cpSync, mkdirSync, existsSync } from 'node:fs';
import { resolve } from 'node:path';

const target = process.argv[2] ?? 'chrome';
const root = resolve(import.meta.dirname, '..');
const distDir = resolve(root, 'dist');

if (!existsSync(distDir)) mkdirSync(distDir, { recursive: true });

const manifestSrc = resolve(root, 'manifests', `${target}.json`);
const manifestDst = resolve(distDir, 'manifest.json');
const manifest = JSON.parse(readFileSync(manifestSrc, 'utf8'));
writeFileSync(manifestDst, JSON.stringify(manifest, null, 2));

// Icons
const iconsSrc = resolve(root, 'icons');
const iconsDst = resolve(distDir, 'icons');
if (existsSync(iconsSrc)) cpSync(iconsSrc, iconsDst, { recursive: true });

console.log(`✓ ${target} manifest + icons copied to dist/`);
