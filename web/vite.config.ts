import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'
import type { Plugin } from 'vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const ROOT = resolve(__dirname, '..')
const CORPUS_DIR = resolve(ROOT, 'data', 'corpus')
const SYNC = resolve(__dirname, 'scripts', 'sync-corpus.mjs')

/**
 * Keeps web/public/corpus in step with data/corpus while the dev server runs.
 *
 * The reports themselves are copied by `predev` and `prebuild`, so this plugin
 * is only about staying current after a regeneration. It does not serve
 * anything. Serving is Vite's ordinary public directory handling, which is
 * what makes the development and production paths identical.
 */
function corpusWatch(): Plugin {
  return {
    name: 'sutra-corpus-watch',
    apply: 'serve',
    configureServer(server) {
      server.watcher.add(CORPUS_DIR)
      const resync = (file: string) => {
        if (!file.endsWith('.json') || !file.startsWith(CORPUS_DIR)) return
        const result = spawnSync(process.execPath, [SYNC], { encoding: 'utf-8' })
        if (result.status === 0) {
          server.config.logger.info(`corpus reports resynced after ${file}`)
          server.ws.send({ type: 'full-reload' })
        } else {
          server.config.logger.error(result.stderr || 'corpus resync failed')
        }
      }
      server.watcher.on('change', resync)
      server.watcher.on('add', resync)
    },
  }
}

export default defineConfig({
  // Relative, not the default '/'.
  //
  // With an absolute base, index.html asks for /assets/index-xxx.js. That only
  // resolves if the bundle is served at the exact root of a domain. Served one
  // level down, which is what several static hosts do, the browser asks the
  // domain root, gets a 404 or an HTML error page, never executes the module,
  // and renders an empty <div id="root">. A white page with no error in it.
  //
  // './' makes every emitted reference relative to index.html, so the bundle
  // works at the root, under a subpath, and from a file:// URL. There is no
  // downside for this project because it is a single page app with hash
  // routing, so index.html is always the document the browser resolves
  // against.
  base: './',
  plugins: [react(), corpusWatch()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: 'dist',
    // Sourcemaps are not shipped. They would be the largest thing in the
    // bundle and they expose the whole source tree on a public URL.
    sourcemap: false,
    assetsInlineLimit: 0,
  },
})
