// Stale-deploy recovery.
//
// A Single-Page App keeps running the JS bundle it was loaded with until a full
// page reload. When a new deploy replaces the hashed bundles/chunks, a tab left
// open across the deploy is "stale": navigating to a lazily-loaded route tries
// to import a chunk that no longer exists on the server. With the server now
// returning an honest 404 for missing /assets/* (see backend handle_404), Vite
// emits a `vite:preloadError` on the window. We recover by reloading ONCE to
// fetch the current build — guarded so a genuine (non-stale) failure can't loop.

const KEY = 'graider:lastStaleReload'
const GUARD_MS = 10_000

// Pure + injectable for testing. Returns true if it triggered a reload.
export function recoverFromStaleChunk(opts = {}) {
  const now = opts.now ?? Date.now()
  const storage = opts.storage ?? (typeof window !== 'undefined' ? window.sessionStorage : null)
  const reload = opts.reload ?? (() => window.location.reload())
  try {
    if (!storage) return false
    const last = Number(storage.getItem(KEY) || 0)
    if (now - last < GUARD_MS) {
      return false // already reloaded very recently — don't loop on a real failure
    }
    storage.setItem(KEY, String(now))
  } catch {
    // sessionStorage unavailable/throws (private mode, sandboxed iframe). Without
    // a persistable guard we can't prevent a reload loop, so don't reload.
    return false
  }
  reload()
  return true
}

export function installStaleChunkRecovery() {
  window.addEventListener('vite:preloadError', (e) => {
    // We handle the failure via reload; prevent Vite's default rethrow.
    if (e && typeof e.preventDefault === 'function') e.preventDefault()
    recoverFromStaleChunk()
  })
}
