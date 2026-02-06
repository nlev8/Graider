import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL || 'https://hecxqiedfodnpujjriin.supabase.co'
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY || 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImhlY3hxaWVkZm9kbnB1ampyaWluIiwicm9sZSI6ImFub24iLCJpYXQiOjE3Njk4OTA3ODMsImV4cCI6MjA4NTQ2Njc4M30.KUvoxjmnCbZSUZo2a8nIj0UD56KM-CXB0dpZ1iYMwLE'

export const supabase = createClient(supabaseUrl, supabaseAnonKey)
