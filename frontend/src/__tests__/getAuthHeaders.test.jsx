import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('../services/supabase', () => ({
  supabase: { auth: { getSession: vi.fn(async () => ({ data: { session: { access_token: 'STALE' } } })) } },
}))

import { getAuthHeaders } from '../services/api'

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
