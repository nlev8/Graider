import { describe, it, expect, vi } from 'vitest'
import { recoverFromStaleChunk } from '../staleChunkRecovery'

function fakeStorage(initial = {}) {
  const m = { ...initial }
  return {
    getItem: (k) => (k in m ? m[k] : null),
    setItem: (k, v) => { m[k] = String(v) },
  }
}

describe('recoverFromStaleChunk (stale-deploy recovery)', () => {
  it('reloads once when there has been no recent reload', () => {
    const reload = vi.fn()
    const storage = fakeStorage()
    const did = recoverFromStaleChunk({ now: 1_000_000, storage, reload })
    expect(did).toBe(true)
    expect(reload).toHaveBeenCalledTimes(1)
    expect(storage.getItem('graider:lastStaleReload')).toBe('1000000')
  })

  it('does NOT reload again within the 10s guard window (no reload loop)', () => {
    const reload = vi.fn()
    const storage = fakeStorage({ 'graider:lastStaleReload': '1000000' })
    const did = recoverFromStaleChunk({ now: 1_005_000, storage, reload }) // +5s
    expect(did).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })

  it('reloads again after the guard window (recovers from a later deploy)', () => {
    const reload = vi.fn()
    const storage = fakeStorage({ 'graider:lastStaleReload': '1000000' })
    const did = recoverFromStaleChunk({ now: 1_011_000, storage, reload }) // +11s
    expect(did).toBe(true)
    expect(reload).toHaveBeenCalledTimes(1)
  })

  it('does NOT reload if storage throws (no unguarded loop in hardened contexts)', () => {
    const reload = vi.fn()
    const throwingStorage = {
      getItem: () => { throw new Error('sessionStorage blocked') },
      setItem: () => { throw new Error('blocked') },
    }
    const did = recoverFromStaleChunk({ now: 1_000_000, storage: throwingStorage, reload })
    expect(did).toBe(false)
    expect(reload).not.toHaveBeenCalled()
  })
})
