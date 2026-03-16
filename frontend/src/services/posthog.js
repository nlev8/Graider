/**
 * PostHog Analytics for Graider App
 * Tracks user behavior to understand product usage patterns.
 */

import posthog from 'posthog-js'

const POSTHOG_KEY = 'phc_lWjzRXIG81gguCXd4yqRv5M4K16rnUr7rYx2plbQLdl'
const POSTHOG_HOST = 'https://us.i.posthog.com'

let initialized = false

export function initPostHog() {
  if (initialized) return
  posthog.init(POSTHOG_KEY, {
    api_host: POSTHOG_HOST,
    person_profiles: 'identified_only',
    autocapture: false,
    capture_pageview: false,
    capture_pageleave: true,
    persistence: 'localStorage',
  })
  initialized = true
}

export function identifyUser(user) {
  if (!user) return
  posthog.identify(user.id, {
    email: user.email,
    created_at: user.created_at,
  })
}

export function resetUser() {
  posthog.reset()
}

export function track(event, properties) {
  if (initialized) posthog.capture(event, properties)
}
