import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('../services/api', () => ({
  __esModule: true,
  // The export under test
  getDistrictAnalytics: vi.fn(async () => ({
    overview: {
      total_teachers: 4,
      total_students: 120,
      total_assessments: 30,
      average_score: 87.5,
      grade_distribution: { A: 10, B: 8, C: 5, D: 2, F: 1 },
    },
    teachers: [{ user_id: 'u1', name: 'Jane', email: 'j@x', classes_count: 3, students_count: 40, assessments_count: 9 }],
    approximate: false,
  })),
  // Every other api export DistrictSetup.jsx references at module load / render time.
  addSsoAdmin: vi.fn(async () => ({})),
  changeDistrictPassword: vi.fn(async () => ({})),
  createAdminInvite: vi.fn(async () => ({})),
  districtAuth: vi.fn(async () => ({})),
  districtLogout: vi.fn(async () => ({})),
  getDistrictConfig: vi.fn(async () => ({})),
  getDistrictConfigStatus: vi.fn(async () => ({})),
  listAdmins: vi.fn(async () => ({ admins: [] })),
  listSsoAdmins: vi.fn(async () => ({ admins: [] })),
  removeSsoAdmin: vi.fn(async () => ({})),
  revokeAdmin: vi.fn(async () => ({})),
  saveDistrictConfig: vi.fn(async () => ({})),
  searchTeachers: vi.fn(async () => ({ teachers: [] })),
  testDistrictConnection: vi.fn(async () => ({})),
}))

import * as api from '../services/api'
import { DistrictAnalyticsSection } from '../components/DistrictSetup'

describe('DistrictAnalyticsSection', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the rollup + a teacher row', async () => {
    render(<DistrictAnalyticsSection isDark={true} />)
    await waitFor(() => expect(screen.getByText(/120/)).toBeTruthy())   // total students
    expect(screen.getByText(/87.5/)).toBeTruthy()                       // average score
    expect(screen.getByText(/Jane/)).toBeTruthy()                       // teacher row
    expect(api.getDistrictAnalytics).toHaveBeenCalled()
  })
})
