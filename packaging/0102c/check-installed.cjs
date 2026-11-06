const assert=require('node:assert/strict'),path=require('node:path')
const [asset,file]=process.argv.slice(2),m=require(path.resolve(file))
const versions={btc:'#privkeyio:26.6.9:0',xbt:'#privkeyio:26.6.9:2',controller:'#privkeyio:0.1.0:0'}
assert.equal(m.manifest.version,versions[asset])
const ids=Object.keys(m.actions.actions)
const node=['migrated-admin-init','migrated-review-incoming','migrated-review-outgoing','migrated-grant-confirm','migrated-grant-cancel','migrated-grant-pause','migrated-grant-credential','migrated-grant-status']
const controller=['migrated-initialize','migrated-pair-forward','migrated-new-forward','migrated-confirm-forward','migrated-cancel-forward','migrated-pair-reverse','migrated-new-reverse','migrated-confirm-reverse','migrated-cancel-reverse','migrated-status','migrated-history','migrated-invoice','migrated-settings']
for(const id of asset==='controller'?controller:node)assert.ok(ids.includes(id),id)
if(asset==='controller')assert.deepEqual(ids.sort(),controller.sort())
else for(const id of ['config','node-info','rescan-blockchain','reset-password'])assert.ok(ids.includes(id),id)
assert.ok(ids.every(id=>!/(pilot|repeat|forward-session|reverse-session)/.test(id)))
assert.equal(m.manifest.canMigrateFrom,asset==='xbt'?'=#privkeyio:26.6.9:1 || =#privkeyio:26.6.9:2':'='+versions[asset])
assert.equal(m.manifest.canMigrateTo,'='+versions[asset])
console.log('PASS: installed '+asset+' registry, exact version and supported update boundaries')
