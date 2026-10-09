import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const meta = (name: string) => async () => ({ name, group: 'Swap Setup',
  description: 'A reusable grant for fixed 1,000 BTC sat to 2,000 XBT sat swaps on the selected channel or explicitly enabled routed channels. New enrollment expires after 24 hours. Each enrollment consumes one slot, including failed or interrupted swaps.',
  warning: 'This grants bounded payment and channel protection authority to the holder. Deadline protection may force-close the original receiving BTC channel and incur on-chain fees. Expiry or pause does not revoke recovery rights for already enrolled swaps.',
  allowedStatuses: 'only-running' as const, visibility: 'enabled' as const })
async function run(effects: any, mode: string, input: object) {
  return sdk.SubContainer.withTemp(effects,{imageId:'lightning'},mainMounts,'swap-session',async sub => {
    const res=await sub.exec(['/opt/xbt-venv/bin/python','/usr/local/libexec/swap_session.py','xbt',rootDir,mode],{input:JSON.stringify(input)})
    let report:any
    try { report=JSON.parse(String(res.stdout)) } catch { throw new Error('Grant operation interrupted. Preserve its records and inspect before retrying.') }
    if(res.exitCode!==0)throw new Error('Grant refused. Finish existing swaps, check the selected channel and restore state. Leave New grant off when recovering an interrupted setup.')
    const labels:Record<string,string>={credential:'Controller grant credential',max_swaps:'Maximum swaps',expires_at:'Enrollment expiry (Unix time)',restart_required:'Restart BTC coordinator required',payment_started:'Payment started',paused:'New enrollments paused',recovery_preserved:'Existing recovery preserved'}
    return {version:'1' as const,title:'XBT Swap Grant',message: mode==='pause' ? 'New enrollments stopped. Keep the controller running to finish already enrolled swaps.' : 'Save this credential in Swap Controller once. Restart the BTC coordinator if indicated, then pair both grants. This action does not send a payment.',
      result:{type:'group' as const,value:Object.entries(report).filter(([k])=>k in labels).map(([k,v])=>({name:labels[k],description:null,type:'single' as const,value:String(v),masked:k==='credential',copyable:k==='credential',qr:false}))}}
  })
}
export const enableSwapSession=sdk.Action.withInput('enable-swap-session',meta('Enable Repeat Swap Grant'),sdk.InputSpec.of({
  routed:sdk.Value.toggle({name:'Allow routed swaps',description:'Explicitly authorize the currently eligible local channels (up to 8). One payment part and one attempt; at most 10 XBT sats routing fee, 80 blocks and 4 hops. Existing direct grants require New grant to change mode.',default:false}),
  channel:sdk.Value.text({name:'Allowed channel short ID (empty: all eligible channels for routed mode, otherwise one channel)',required:false,masked:false,default:null,placeholder:null}),
  maxSwaps:sdk.Value.number({name:'Maximum swaps (1–10)',required:true,integer:true,min:1,max:10,default:5,placeholder:null}),
  newGrant:sdk.Value.toggle({name:'Replace a previous grant with a new 24-hour budget',description:'Only after every previous enrollment has finished. Leave off to retrieve the current grant without changing its budget.',default:false}),
  confirmed:sdk.Value.toggle({name:'Authorize this channel and budget for fixed-rate swaps and deadline protection',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'enable',{...input,channel:input.channel??''}))
export const pauseSwapSession=sdk.Action.withInput('pause-swap-session',meta('Pause New Swap Enrollments'),sdk.InputSpec.of({
  confirmed:sdk.Value.toggle({name:'Pause new enrollments; keep existing recovery enabled',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'pause',input))
