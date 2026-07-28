/**
 * A deliberately stupid static file server for dist.
 *
 * No bundler, no middleware, no SPA rewrite, no framework. It reads a file off
 * disk and returns it, which is what Catalyst Web Client Hosting does. If the
 * page works here it works there, and if it needs anything cleverer than this
 * then it is not a static bundle and it will not deploy.
 *
 *   node scripts/serve-static.mjs [port]
 */

import { createServer } from 'node:http'
import { readFileSync, existsSync, statSync } from 'node:fs'
import { resolve, dirname, extname, normalize } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const DIST = resolve(here, '..', 'dist')
const port = Number(process.argv[2] ?? 4173)

const TYPES = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.woff2': 'font/woff2',
  '.svg': 'image/svg+xml',
  '.md': 'text/plain; charset=utf-8',
  '.txt': 'text/plain; charset=utf-8',
}

if (!existsSync(DIST)) {
  console.error('dist not found. Run: npm run build')
  process.exit(1)
}

const server = createServer((req, res) => {
  const url = (req.url ?? '/').split('?')[0]
  const path = url === '/' ? '/index.html' : url
  const file = resolve(DIST, `.${normalize(path)}`)

  // Never serve outside dist.
  if (!file.startsWith(DIST)) {
    res.writeHead(403).end('forbidden')
    return
  }
  if (!existsSync(file) || statSync(file).isDirectory()) {
    res.writeHead(404, { 'content-type': 'text/plain' }).end('404')
    return
  }

  // A CSP close to what Catalyst enforces, so a blocked request fails here
  // rather than after deployment.
  res.writeHead(200, {
    'content-type': TYPES[extname(file)] ?? 'application/octet-stream',
    'content-security-policy':
      "default-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data:; script-src 'self'",
  })
  res.end(readFileSync(file))
})

server.listen(port, '0.0.0.0', () => {
  console.log(`static server, no backend, serving ${DIST}`)
  console.log(`http://localhost:${port}`)
})
