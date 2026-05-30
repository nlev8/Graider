import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../services/supabase', () => ({
  supabase: { auth: { getSession: vi.fn(async () => ({ data: { session: { access_token: 'STALE' } } })) } },
}))

import { getAuthHeaders, isSsoUser } from '../services/api'

describe('getAuthHeaders', () => {
  beforeEach(() => { window.__graiderUser = undefined })

  it('skips Bearer for a ClassLink UUID session via auth_source', async () => {
    window.__graiderUser = { id: '11111111-1111-1111-1111-111111111111', auth_source: 'classlink' }
    expect(await getAuthHeaders()).toEqual({})
  })

  it('skips Bearer for unlinked Clever via id prefix (fallback)', async () => {
    window.__graiderUser = { id: 'clever:abc' }
    expect(await getAuthHeaders()).toEqual({})
  })

  it('sends Bearer for a normal Supabase user', async () => {
    window.__graiderUser = { id: 'real-user' }
    expect(await getAuthHeaders()).toEqual({ Authorization: 'Bearer STALE' })
  })
})

describe('isSsoUser', () => {
  it('true for classlink auth_source (UUID id)', () => {
    expect(isSsoUser({ id: '11111111-1111-1111-1111-111111111111', auth_source: 'classlink' })).toBe(true)
  })
  it('true for clever auth_source', () => {
    expect(isSsoUser({ id: 'x', auth_source: 'clever' })).toBe(true)
  })
  it('true for clever: id prefix fallback', () => {
    expect(isSsoUser({ id: 'clever:abc' })).toBe(true)
  })
  it('false for a normal supabase user', () => {
    expect(isSsoUser({ id: 'real-user' })).toBe(false)
  })
  it('false for undefined', () => {
    expect(isSsoUser(undefined)).toBe(false)
  })
})
