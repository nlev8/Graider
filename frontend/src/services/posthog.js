/**
 * PostHog Analytics for Graider App
 * Tracks user behavior to understand product usage patterns.
 */

import posthog from 'posthog-js'

const POSTHOG_KEY = 'phc_lWjzRXIG81gguCXd4yqRv5M4K16rnUr7rYx2plbQLdl'
const POSTHOG_HOST = 'https://us.i.posthog.com'

let initialized = false
let disabled = false

export function initPostHog() {
  // Districts can disable analytics by setting GRAIDER_DISABLE_ANALYTICS=true
  // or by adding ?analytics=off to the URL
  if (window.GRAIDER_DISABLE_ANALYTICS || localStorage.getItem('graider_analytics_disabled') === 'true') {
    disabled = true
    return
  }
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

export function disableAnalytics() {
  disabled = true
  localStorage.setItem('graider_analytics_disabled', 'true')
  if (initialized) posthog.opt_out_capturing()
}

export function identifyUser(user) {
  if (disabled || !user) return
  posthog.identify(user.id, {
    email: user.email,
    created_at: user.created_at,
  })
}

export function resetUser() {
  posthog.reset()
}

export function track(event, properties) {
  if (initialized && !disabled) posthog.capture(event, properties)
}
