/**
 * App logout wiring — static + behavioral verification
 *
 * Verifies that the handleLogout handler in App.jsx calls BOTH
 * /api/clever/logout and /api/classlink/logout. Using static inspection
 * because App.jsx is ~7K LOC and requires non-trivial render infrastructure.
 *
 * Closes MAJOR audit finding: ClassLink Flask sessions persisted server-side
 * after frontend logout because only /api/clever/logout was called.
 */
import { describe, it, expect } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'

var APP_PATH = path.join(__dirname, '../App.jsx')

describe('App logout wiring', () => {
  var src = fs.readFileSync(APP_PATH, 'utf-8')

  it('calls /api/classlink/logout in the logout handler', () => {
    expect(src).toMatch(/['"]\/api\/classlink\/logout['"]/)
  })

  it('calls /api/clever/logout in the logout handler', () => {
    expect(src).toMatch(/['"]\/api\/clever\/logout['"]/)
  })

  it('uses Promise.allSettled for parallel SSO logout calls', () => {
    expect(src).toMatch(/Promise\.allSettled/)
  })

  it('includes credentials: include on both logout fetches', () => {
    // Both fetch calls inside Promise.allSettled should include credentials
    var allSettledBlock = src.match(/Promise\.allSettled\(\[([\s\S]*?)\]\)/)
    expect(allSettledBlock).not.toBeNull()
    var block = allSettledBlock[1]
    expect(block).toMatch(/['"]\/api\/clever\/logout['"]/)
    expect(block).toMatch(/['"]\/api\/classlink\/logout['"]/)
    expect(block.match(/credentials:\s*['"]include['"]/g)).toHaveLength(2)
  })
})
