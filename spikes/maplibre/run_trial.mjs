import { createServer } from 'node:http';
import { readFile, stat } from 'node:fs/promises';
import { extname, join, normalize } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium } from 'playwright';

const ROOT = fileURLToPath(new URL('.', import.meta.url));
const EXPECTED_MAPLIBRE_VERSION = '6.11.2';
const MIME = new Map([
  ['.html', 'text/html; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'],
  ['.mjs', 'text/javascript; charset=utf-8'],
  ['.css', 'text/css; charset=utf-8'],
  ['.json', 'application/json; charset=utf-8'],
  ['.map', 'application/json; charset=utf-8'],
  ['.png', 'image/png'],
  ['.svg', 'image/svg+xml']
]);

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function safePath(urlPath) {
  const raw = decodeURIComponent(urlPath.split('?')[0]);
  const relative = raw === '/' ? 'trial.html' : raw.replace(/^\/+/, '');
  const resolved = normalize(join(ROOT, relative));
  assert(resolved.startsWith(normalize(ROOT)), 'path escaped trial root');
  return resolved;
}

const maplibrePackage = JSON.parse(
  await readFile(join(ROOT, 'node_modules/maplibre-gl/package.json'), 'utf8')
);
assert(
  maplibrePackage.version === EXPECTED_MAPLIBRE_VERSION,
  `MapLibre version mismatch: expected ${EXPECTED_MAPLIBRE_VERSION}, got ${maplibrePackage.version}`
);

const server = createServer(async (request, response) => {
  try {
    const path = safePath(request.url || '/');
    const info = await stat(path);
    if (!info.isFile()) throw new Error('not a file');
    const body = await readFile(path);
    response.writeHead(200, {
      'content-type': MIME.get(extname(path)) || 'application/octet-stream',
      'cache-control': 'no-store'
    });
    response.end(body);
  } catch {
    response.writeHead(404, { 'content-type': 'text/plain; charset=utf-8' });
    response.end('not found');
  }
});

await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
const address = server.address();
assert(address && typeof address === 'object', 'trial server did not bind');
const origin = `http://127.0.0.1:${address.port}`;

let browser;
try {
  browser = await chromium.launch({
    headless: true,
    args: ['--use-gl=swiftshader', '--enable-webgl']
  });
  const page = await browser.newPage({ viewport: { width: 1200, height: 800 } });
  const externalRequests = [];
  const consoleErrors = [];
  const pageErrors = [];

  page.on('request', (request) => {
    const url = request.url();
    if (!url.startsWith(origin) && !url.startsWith('data:') && !url.startsWith('blob:')) {
      externalRequests.push(url);
    }
  });
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text());
  });
  page.on('pageerror', (error) => pageErrors.push(String(error)));

  const response = await page.goto(`${origin}/trial.html`, { waitUntil: 'load' });
  assert(response?.ok(), `trial page failed to load: ${response?.status()}`);
  await page.waitForFunction(() => window.__SDA_MAP_READY__ === true, null, { timeout: 30000 });

  const result = await page.evaluate(() => ({
    result: window.__SDA_MAP_RESULT__,
    error: window.__SDA_MAP_ERROR__ || null,
    bodyText: document.body.innerText,
    canvasCount: document.querySelectorAll('#map canvas').length,
    fallbackItems: [...document.querySelectorAll('#fallback li')].map((node) => ({
      featureId: node.dataset.featureId,
      text: node.textContent,
      citationCount: Number(node.querySelector('.citations')?.dataset.citationCount || '0'),
      evidenceIds: [...node.querySelectorAll('.citations a')].map((anchor) => anchor.dataset.evidenceId),
      documentIds: [...node.querySelectorAll('.citations a')].map((anchor) => anchor.dataset.documentId),
      sourceIds: [...node.querySelectorAll('.citations a')].map((anchor) => anchor.dataset.sourceId)
    }))
  }));

  assert(!result.error, `MapLibre emitted an error: ${result.error}`);
  assert(result.result?.rendererContract === 'sda-public-map-v0.1', 'renderer contract changed');
  assert(result.result?.featureCount === 1, 'unexpected GeoJSON feature count');
  assert(result.result?.renderedFeatureCount >= 1, 'MapLibre did not render the public facility feature');
  assert(result.result?.styleSourceIds.length === 1, 'unexpected MapLibre style source count');
  assert(result.result?.styleSourceIds[0] === 'sda-public-facilities', 'unexpected MapLibre source identity');
  assert(result.canvasCount === 1 && result.result?.canvasPresent, 'MapLibre canvas was not created');
  assert(result.result?.fallbackCount === 1, 'semantic fallback count does not match map features');
  assert(result.bodyText.includes('منشأة تدريب تجريبية'), 'Arabic facility label missing from semantic fallback');
  assert(result.bodyText.includes('Trial Training Facility'), 'English facility label missing from semantic fallback');
  assert(result.fallbackItems[0]?.citationCount >= 1, 'semantic fallback lost supporting citation count');
  assert(result.fallbackItems[0]?.evidenceIds.includes('SDA-EVID-TRIAL-MAP'), 'Evidence identity missing from fallback');
  assert(result.fallbackItems[0]?.documentIds.includes('SDA-DOC-TRIAL-MAP'), 'Document identity missing from fallback');
  assert(result.fallbackItems[0]?.sourceIds.includes('SDA-SOURCE-TRIAL-MAP'), 'Source identity missing from fallback');
  assert(!/\b[QP]\d+\b/.test(result.bodyText), 'backend Q/P identifier leaked into rendered page');
  assert(externalRequests.length === 0, `external network requests detected: ${externalRequests.join(', ')}`);
  assert(consoleErrors.length === 0, `browser console errors: ${consoleErrors.join(' | ')}`);
  assert(pageErrors.length === 0, `browser page errors: ${pageErrors.join(' | ')}`);

  const evidence = {
    status: 'PASS',
    maplibre_version: maplibrePackage.version,
    renderer_contract: result.result.rendererContract,
    feature_count: result.result.featureCount,
    rendered_feature_count: result.result.renderedFeatureCount,
    source_ids: result.result.styleSourceIds,
    layer_ids: result.result.styleLayerIds,
    semantic_fallback_count: result.result.fallbackCount,
    external_network_request_count: externalRequests.length,
    arabic_label_verified: true,
    english_label_verified: true,
    supporting_evidence_identity_verified: true,
    installed_version_verified: true,
    tile_provider_selected: false,
    geocoder_selected: false
  };
  console.log(JSON.stringify(evidence, null, 2));
} finally {
  if (browser) await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
