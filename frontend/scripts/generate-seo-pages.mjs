// Runs after `vite build`: writes the static requirement pages, 404.html and sitemap.xml into build/.
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildPages, notFoundPage, sitemap } from './seo-pages.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const outDir = join(root, 'build');
const data = JSON.parse(readFileSync(join(root, 'seo', 'programs.json'), 'utf8'));

// Bump when the homepage copy changes; program pages are dated by the catalog data.
const HOME_LASTMOD = '2026-10-11';

const pages = buildPages(data);
for (const { path, html } of pages) {
  // <path>/index.html, served at <path> (vercel.json sets trailingSlash: false).
  const file = join(outDir, path, 'index.html');
  mkdirSync(dirname(file), { recursive: true });
  writeFileSync(file, html);
}
writeFileSync(join(outDir, '404.html'), notFoundPage());
writeFileSync(
  join(outDir, 'sitemap.xml'),
  sitemap(pages.map((page) => page.path), { homeDate: HOME_LASTMOD, contentDate: data.catalog_date || HOME_LASTMOD }),
);

console.log(`SEO pages: wrote ${pages.length} pages, 404.html and sitemap.xml to build/.`);
