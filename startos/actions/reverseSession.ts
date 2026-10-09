import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const meta = (name: string) => async () => ({ name, group: 'Swap Setup',
  description: 'A reusable grant for fixed 3,000 XBT sat to 1,500 BTC sat swaps on the currently eligible channels (up to 8). New grants allow up to 288 blocks of BTC route delay. Existing 80- and 144-block grants keep their limit until explicitly replaced. New enrollment expires after 24 hours. Each enrollment consumes one slot, including failed or interrupted swaps.',
  warning: 'This grants bounded payment and channel protection authority to the holder. Deadline protection may force-close the original receiving XBT channel and incur on-chain fees. Expiry or pause does not revoke recovery rights for already enrolled swaps.',
  allowedStatuses: 'only-running' as const, visibility: 'enabled' as const })
async function run(effects: any, mode: string, input: object) {
  return sdk.SubContainer.withTemp(effects,{imageId:'lightning'},mainMounts,'reverse-session',async sub => {
    const res=await sub.exec(['/opt/xbt-venv/bin/python','/usr/local/libexec/reverse_session.py','xbt',rootDir,mode],{input:JSON.stringify(input)})
    let report:any
    try { report=JSON.parse(String(res.stdout)) } catch { throw new Error('Grant operation interrupted. Preserve its records and inspect before retrying.') }
    if(res.exitCode!==0)throw new Error('Reverse grant refused. Finish swaps in both directions; check channels, restore state and explicit XBT gate activation. Leave New grant off when recovering an interrupted setup.')
    const labels:Record<string,string>={credential:'Controller grant credential',max_swaps:'Maximum swaps',max_delay_blocks:'Maximum BTC route delay (blocks)',expires_at:'Enrollment expiry (Unix time)',restart_required:'Restart BTC coordinator required',payment_started:'Payment started',paused:'New enrollments paused',recovery_preserved:'Existing recovery preserved'}
    return {version:'1' as const,title:'XBT Reverse Swap Grant',message: mode==='pause' ? 'New enrollments stopped. Keep the controller running to finish already enrolled swaps.' : 'Save this credential under Pair Reverse Swap Grants in Swap Controller. This action does not send a payment.',
      result:{type:'group' as const,value:Object.entries(report).filter(([k])=>k in labels).map(([k,v])=>({name:labels[k],description:null,type:'single' as const,value:String(v),masked:k==='credential',copyable:k==='credential',qr:false}))}}
  })
}
export const enableReverseSession=sdk.Action.withInput('enable-reverse-session',meta('Enable Reverse Swap Grant'),sdk.InputSpec.of({
  maxSwaps:sdk.Value.number({name:'Maximum swaps (1–10)',required:true,integer:true,min:1,max:10,default:5,placeholder:null}),
  newGrant:sdk.Value.toggle({name:'Replace a previous grant with a new 24-hour budget',description:'Only after every previous enrollment has finished. Leave off to retrieve the current grant without changing its budget.',default:false}),
  confirmed:sdk.Value.toggle({name:'Authorize 3,000 XBT → 1,500 BTC swaps: up to 10 BTC sats routing fee, 288 blocks for new grants, 4 hops, one part and attempt',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'enable',{...input,channel:'',routed:true,maxDelay:288}))
export const pauseReverseSession=sdk.Action.withInput('pause-reverse-session',meta('Pause Reverse Swap Enrollments'),sdk.InputSpec.of({
  confirmed:sdk.Value.toggle({name:'Pause new enrollments; keep existing recovery enabled',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'pause',input))
