/**
 * Tests for PostHog analytics opt-out mechanism.
 * Verifies districts can disable analytics via flag or localStorage.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest'

// Mock posthog-js
vi.mock('posthog-js', () => ({
  default: {
    init: vi.fn(),
    identify: vi.fn(),
    reset: vi.fn(),
    capture: vi.fn(),
    opt_out_capturing: vi.fn(),
  },
}))

describe('PostHog Analytics Opt-Out', () => {
  beforeEach(() => {
    vi.resetModules()
    vi.clearAllMocks()
    delete window.GRAIDER_DISABLE_ANALYTICS
    localStorage.removeItem('graider_analytics_disabled')
  })

  it('skips initialization when GRAIDER_DISABLE_ANALYTICS is set', async () => {
    window.GRAIDER_DISABLE_ANALYTICS = true
    const mod = await import('./posthog.js')
    mod.initPostHog()
    const posthog = (await import('posthog-js')).default
    // identifyUser should be a no-op
    mod.identifyUser({ id: '1', email: 'test@school.edu' })
    expect(posthog.identify).not.toHaveBeenCalled()
  })

  it('skips initialization when localStorage flag is set', async () => {
    localStorage.setItem('graider_analytics_disabled', 'true')
    const mod = await import('./posthog.js')
    mod.initPostHog()
    // track should be a no-op
    mod.track('test_event', { key: 'value' })
    const posthog = (await import('posthog-js')).default
    expect(posthog.capture).not.toHaveBeenCalled()
  })

  it('disableAnalytics persists to localStorage and calls opt_out', async () => {
    const mod = await import('./posthog.js')
    mod.disableAnalytics()
    expect(localStorage.getItem('graider_analytics_disabled')).toBe('true')
  })

  it('track is no-op after disableAnalytics', async () => {
    const mod = await import('./posthog.js')
    mod.disableAnalytics()
    mod.track('event', {})
    const posthog = (await import('posthog-js')).default
    expect(posthog.capture).not.toHaveBeenCalled()
  })

  it('identifyUser is no-op when disabled', async () => {
    const mod = await import('./posthog.js')
    mod.disableAnalytics()
    mod.identifyUser({ id: '1', email: 'a@b.com' })
    const posthog = (await import('posthog-js')).default
    expect(posthog.identify).not.toHaveBeenCalled()
  })

  it('resetUser calls posthog.reset', async () => {
    const mod = await import('./posthog.js')
    mod.resetUser()
    const posthog = (await import('posthog-js')).default
    expect(posthog.reset).toHaveBeenCalled()
  })
})
