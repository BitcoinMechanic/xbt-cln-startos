const { mkdtempSync, rmSync } = require('node:fs')
const { tmpdir } = require('node:os')
const { join } = require('node:path')
const { execFileSync } = require('node:child_process')
const out = mkdtempSync(join(tmpdir(), 'xbt-wrapper-test-'))
try {
  execFileSync(process.execPath, [require.resolve('typescript/bin/tsc'),
    'startos/xbt-policy.ts', 'startos/xbt-policy.test.ts', '--ignoreConfig',
    '--outDir', out, '--module', 'commonjs', '--target', 'es2022',
    '--skipLibCheck', '--esModuleInterop', '--types', 'node'], { stdio: 'inherit' })
  execFileSync(process.execPath, [join(out, 'xbt-policy.test.js')], { stdio: 'inherit' })
} finally {
  rmSync(out, { recursive: true, force: true })
}

execFileSync(process.execPath, ['scripts/test-recovery-topology.cjs'], { stdio: 'inherit' })

execFileSync(process.execPath, ['scripts/test-controller-interface.cjs'], { stdio: 'inherit' })

execFileSync(process.execPath, ['scripts/test-gate-integration.cjs'], { stdio: 'inherit' })
