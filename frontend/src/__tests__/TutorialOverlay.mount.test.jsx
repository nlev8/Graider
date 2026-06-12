import React from 'react'
import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi, afterEach } from 'vitest'

// Render-time smoke test for TutorialOverlay. Added with the CQ wave-7 split
// of TutorialOverlay.jsx into tutorial-overlay/* (mirrors
// AssistantChat.mount.test.jsx from the wave-3 split, for the same reason):
// build + unit tests pass even if a split leaves an unimported component or
// mis-threaded prop that white-screens the overlay at runtime. This asserts
// real step content (title, description, counter, nav buttons) renders
// through the extracted steps.js -> shell -> TutorialTooltip chain, and that
// the spotlight SVG layer mounts.

describe('TutorialOverlay mounts without crashing (render-time smoke)', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  const renderOverlay = async (props = {}) => {
    const mod = await import('../components/TutorialOverlay')
    const TutorialOverlay = mod.default
    const handlers = {
      currentStep: 0,
      onNext: vi.fn(),
      onBack: vi.fn(),
      onSkip: vi.fn(),
      setActiveTab: vi.fn(),
      setSettingsTab: vi.fn(),
      setPlannerMode: vi.fn(),
      ...props,
    }
    const utils = render(React.createElement(TutorialOverlay, handlers))
    return { ...utils, handlers, TUTORIAL_STEPS: mod.TUTORIAL_STEPS }
  }

  it('renders step 1 content: title, description, counter, nav buttons, spotlight svg', async () => {
    const { container, TUTORIAL_STEPS } = await renderOverlay()

    // Tooltip is hidden while `transitioning` (250ms measure timer) — wait it out.
    expect(await screen.findByText('Your Workspace')).toBeTruthy()
    expect(
      screen.getByText(/This sidebar is your main navigation/)
    ).toBeTruthy()
    expect(
      screen.getByText(`Step 1 of ${TUTORIAL_STEPS.length}`)
    ).toBeTruthy()
    expect(screen.getByText('Next')).toBeTruthy()
    expect(screen.getByText('Skip tour')).toBeTruthy()
    // Step 0 is the first step: no Back button.
    expect(screen.queryByText('Back')).toBeNull()

    // Spotlight layer (SVG backdrop with cutout path) mounted.
    const svg = container.querySelector('svg path[fill-rule="evenodd"]')
    expect(svg).toBeTruthy()
  })

  it('wires nav handlers: Next -> onNext, Skip tour -> onSkip, Back appears mid-tour', async () => {
    const { handlers } = await renderOverlay({ currentStep: 1 })

    expect(await screen.findByText('Toolbar: Start Grading & Auto-Grade')).toBeTruthy()
    // Step 1 switches to the grade tab via the shell effect.
    expect(handlers.setActiveTab).toHaveBeenCalledWith('grade')

    fireEvent.click(screen.getByText('Next'))
    expect(handlers.onNext).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText('Back'))
    expect(handlers.onBack).toHaveBeenCalledTimes(1)

    fireEvent.click(screen.getByText('Skip tour'))
    expect(handlers.onSkip).toHaveBeenCalledTimes(1)
  })

  it('shows Get Started on the final step', async () => {
    const { TUTORIAL_STEPS } = await import('../components/tutorial-overlay/steps')
    const { handlers } = await renderOverlay({
      currentStep: TUTORIAL_STEPS.length - 1,
    })
    expect(await screen.findByText('Get Started')).toBeTruthy()
    fireEvent.click(screen.getByText('Get Started'))
    expect(handlers.onSkip).toHaveBeenCalledTimes(1)
  })
})
