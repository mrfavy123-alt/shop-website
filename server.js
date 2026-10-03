import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer } from 'node:http';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { handleApi } from './api-lib.js';

const root = path.dirname(fileURLToPath(import.meta.url));
const port = Number(process.env.PORT || 8000);
const apiRoutes = new Set([
  '/api/config', '/api/products', '/api/checkout', '/api/bookings', '/api/contact',
  '/api/training-enrollments', '/api/training-payments/initialize', '/api/training-payments/verify',
]);
const contentTypes = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.ico': 'image/x-icon',
};

function sendJson(response, status, data) {
  const body = JSON.stringify(data);
  response.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(body),
    'Cache-Control': 'no-store',
  });
  response.end(body);
}

async function apiRequest(request, response, route) {
  if (!apiRoutes.has(route)) return sendJson(response, 404, { error: 'Not found' });
  if (!['GET', 'POST'].includes(request.method)) return sendJson(response, 405, { error: 'Method not allowed.' });
  const chunks = [];
  let length = 0;
  for await (const chunk of request) {
    length += chunk.length;
    if (length > 32_000) return sendJson(response, 413, { error: 'Request is too large.' });
    chunks.push(chunk);
  }
  const headers = new Headers();
  for (const [key, value] of Object.entries(request.headers)) {
    if (Array.isArray(value)) headers.set(key, value.join(', '));
    else if (value !== undefined) headers.set(key, value);
  }
  const body = length ? Buffer.concat(chunks) : undefined;
  const webRequest = new Request(`http://${request.headers.host || 'localhost'}${request.url}`, {
    method: request.method,
    headers,
    ...(body ? { body } : {}),
  });
  const result = await handleApi(webRequest, route);
  const responseHeaders = Object.fromEntries(result.headers.entries());
  response.writeHead(result.status, responseHeaders);
  response.end(Buffer.from(await result.arrayBuffer()));
}

function staticFile(request, response) {
  let pathname;
  try {
    pathname = decodeURIComponent(new URL(request.url, 'http://localhost').pathname);
  } catch {
    response.writeHead(400).end('Bad request');
    return;
  }
  if (pathname === '/') pathname = '/index.html';
  const file = path.resolve(root, `.${pathname}`);
  if (!file.startsWith(`${root}${path.sep}`) || !existsSync(file) || !statSync(file).isFile()) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' }).end('Not found');
    return;
  }
  response.writeHead(200, {
    'Content-Type': contentTypes[path.extname(file).toLowerCase()] || 'application/octet-stream',
    'Cache-Control': 'no-cache',
  });
  if (request.method === 'HEAD') response.end();
  else createReadStream(file).pipe(response);
}

createServer(async (request, response) => {
  try {
    const route = new URL(request.url, 'http://localhost').pathname;
    if (route.startsWith('/api/')) await apiRequest(request, response, route);
    else if (request.method === 'GET' || request.method === 'HEAD') staticFile(request, response);
    else response.writeHead(405).end('Method not allowed');
  } catch (error) {
    console.error('Shop server error:', error);
    if (!response.headersSent) sendJson(response, 500, { error: 'We could not complete your request. Please try again.' });
    else response.destroy(error);
  }
}).listen(port, '0.0.0.0', () => {
  console.log(`Zamac Füds running at http://localhost:${port}`);
});
