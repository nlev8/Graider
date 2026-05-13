import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  // Don't pass empty strings to createClient — supabase-js throws
  // `Error: supabaseUrl is required` at module load, which prevents
  // React from mounting (surfaces as a blank dark-blue page in CI
  // test builds without env vars; tracked in #362).
  //
  // Instead, fall through to dummy values below. The resulting client
  // has the full Supabase API surface (no manual stub to maintain),
  // returns `{ data: { session: null } }` from getSession() because
  // there's no auth state in localStorage, and surfaces clear network
  // errors on actual login attempts (clicks on LoginScreen). That's a
  // visible failure for a misconfigured prod deploy, not silent or
  // crashing.
  //
  // Production (Railway) has VITE_SUPABASE_URL + VITE_SUPABASE_ANON_KEY
  // set, so this branch is never reached there. CI's frontend build
  // step doesn't set them, hence the dummy fallback.
  console.error(
    'Missing Supabase configuration — using dummy values. ' +
    'Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY for real auth. ' +
    'In CI test builds this is expected.'
  )
}

export const supabase = createClient(
  supabaseUrl || 'https://dummy.supabase.co',
  supabaseAnonKey || 'dummy-anon-key'
)
