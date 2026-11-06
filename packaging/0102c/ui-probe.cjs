// Read-only fingerprints of the built UI and its runtime; no app startup.
const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')
const result = {}
function walk(p) {
  const st = fs.lstatSync(p)
  if (st.isDirectory()) for (const name of fs.readdirSync(p).sort()) walk(path.join(p, name))
  else if (st.isFile()) result[p.replace(/^\//, '')] = crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')
  else throw Error('Unexpected UI build entry: ' + p)
}
for (const p of ['/usr/local/bin/node', '/app/apps/backend/dist', '/app/apps/frontend/build',
                  '/app/apps/backend/package.json', '/app/apps/frontend/package.json']) walk(p)
if (Object.keys(result).length < 10) throw Error('Incomplete UI image')
process.stdout.write(JSON.stringify(result))
