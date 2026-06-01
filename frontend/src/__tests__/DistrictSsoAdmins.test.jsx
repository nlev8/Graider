import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

vi.mock('../services/api', () => ({
  __esModule: true,
  listSsoAdmins: vi.fn(async () => ({ admins: [{ email: 'a@b.com', tier: 'school', school: 'Lincoln' }] })),
  addSsoAdmin: vi.fn(async () => ({ status: 'saved' })),
  removeSsoAdmin: vi.fn(async () => ({ status: 'removed' })),
}))

import * as api from '../services/api'
import { SsoAdminSection } from '../components/DistrictSetup'

describe('SsoAdminSection', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists existing designations', async () => {
    render(<SsoAdminSection isDark={true} />)
    await waitFor(() => expect(screen.getByText(/a@b.com/)).toBeTruthy())
  })

  it('adds a designation', async () => {
    render(<SsoAdminSection isDark={true} />)
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: 'x@y.com' } })
    fireEvent.click(screen.getByText(/^add$/i))
    await waitFor(() => expect(api.addSsoAdmin).toHaveBeenCalled())
  })

  it('removes a designation', async () => {
    render(<SsoAdminSection isDark={true} />)
    await waitFor(() => expect(screen.getByText(/a@b.com/)).toBeTruthy())
    fireEvent.click(screen.getByText(/^remove$/i))
    await waitFor(() => expect(api.removeSsoAdmin).toHaveBeenCalledWith('a@b.com'))
  })
})
