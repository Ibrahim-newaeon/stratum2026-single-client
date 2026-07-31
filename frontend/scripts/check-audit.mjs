#!/usr/bin/env node
/**
 * npm dependency audit with a documented allowlist.
 *
 * `npm audit` has no native ignore mechanism, so the CI step used to be a bare
 * `npm audit --audit-level=high --omit=dev`. The moment one unfixable advisory
 * lands, that gate can only be satisfied by deleting it or appending `|| true`
 * — both of which silently stop checking everything else.
 *
 * This keeps the gate active for every advisory EXCEPT the ones explicitly
 * listed in .audit-allowlist.json with a reason and a removal condition. A new
 * high/critical advisory still fails the build.
 *
 * Also reports allowlist entries that no longer match anything, so stale
 * suppressions get deleted instead of quietly outliving the vulnerability.
 *
 * Exit codes: 0 clean or fully allowlisted, 1 unallowed advisory found,
 * 2 the audit itself could not be run (never treated as a pass).
 */

import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const root = join(here, '..')
const BLOCKING = new Set(['high', 'critical'])

function loadAllowlist() {
  try {
    const raw = readFileSync(join(root, '.audit-allowlist.json'), 'utf8')
    return JSON.parse(raw).allow ?? {}
  } catch (err) {
    if (err.code === 'ENOENT') return {}
    console.error(`Could not parse .audit-allowlist.json: ${err.message}`)
    process.exit(2)
  }
}

function runAudit() {
  // npm audit exits non-zero when it finds anything at/above the threshold,
  // so a throw is the normal path — the JSON on stdout is what matters.
  try {
    return execFileSync('npm', ['audit', '--omit=dev', '--json'], {
      cwd: root,
      encoding: 'utf8',
      maxBuffer: 32 * 1024 * 1024,
    })
  } catch (err) {
    if (err.stdout) return err.stdout
    console.error(`npm audit could not be run: ${err.message}`)
    process.exit(2)
  }
}

/** Collect the GHSA ids backing a vulnerability, following package-name links. */
function advisoryIds(name, vulns, seen = new Set()) {
  if (seen.has(name)) return []
  seen.add(name)
  const node = vulns[name]
  if (!node) return []
  const ids = []
  for (const via of node.via ?? []) {
    if (typeof via === 'string') {
      ids.push(...advisoryIds(via, vulns, seen)) // vulnerable *through* another package
    } else if (via.url) {
      const m = via.url.match(/(GHSA-[\w-]+)/)
      if (m) ids.push(m[1])
    }
  }
  return ids
}

const allow = loadAllowlist()
let report
try {
  report = JSON.parse(runAudit())
} catch (err) {
  console.error(`npm audit produced unparseable output: ${err.message}`)
  process.exit(2)
}

const vulns = report.vulnerabilities ?? {}
const unallowed = []
const usedIds = new Set()

for (const [name, node] of Object.entries(vulns)) {
  if (!BLOCKING.has(node.severity)) continue
  const ids = advisoryIds(name, vulns)
  // Only skip when EVERY advisory behind this package is allowlisted; a
  // package with one allowed and one new advisory must still fail.
  const notAllowed = ids.filter((id) => !(id in allow))
  ids.filter((id) => id in allow).forEach((id) => usedIds.add(id))
  if (ids.length === 0 || notAllowed.length > 0) {
    unallowed.push(`${name} (${node.severity}): ${notAllowed.join(', ') || 'no advisory id resolved'}`)
  }
}

for (const id of Object.keys(allow)) {
  if (!usedIds.has(id)) {
    console.log(`note: allowlist entry ${id} matched nothing — it can probably be removed.`)
  }
}

if (unallowed.length > 0) {
  console.error('::error::Unallowed high/critical npm advisories:')
  unallowed.forEach((line) => console.error(`  - ${line}`))
  console.error('\nFix the dependency, or add the advisory to')
  console.error('frontend/.audit-allowlist.json with a reason and a removeWhen condition.')
  process.exit(1)
}

const allowed = [...usedIds]
console.log(
  allowed.length > 0
    ? `npm audit clean (allowlisted: ${allowed.join(', ')})`
    : 'npm audit clean (no high/critical advisories)'
)
