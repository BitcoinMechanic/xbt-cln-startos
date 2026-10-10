import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const meta = (name: string) => async () => ({ name, group: 'Swap Grants',
  description: 'A reusable grant for Neoxa market-priced swaps with explicit amount limits, or the existing fixed 3,000 XBT sat to 1,500 BTC sat swaps on the currently eligible channels (up to 8). New grants allow up to 288 blocks of BTC route delay. Existing 80- and 144-block grants keep their limit until explicitly replaced. New enrollment expires after 24 hours. Each enrollment consumes one slot, including failed or interrupted swaps.',
  warning: 'This grants bounded payment and channel protection authority to the holder. Deadline protection may force-close the original receiving XBT channel and incur on-chain fees. Expiry or pause does not revoke recovery rights for already enrolled swaps.',
  allowedStatuses: 'only-running' as const, visibility: 'enabled' as const })
function marketLimits(input:any) { return input.market ? {max_btc_msat:input.maxBtcSats*1000,max_xbt_msat:input.maxXbtSats*1000,total_btc_msat:input.totalBtcSats*1000,total_xbt_msat:input.totalXbtSats*1000} : null }
function grantInput(input:any) { const {market,maxBtcSats,maxXbtSats,totalBtcSats,totalXbtSats,...rest}=input; return {...rest,marketLimits:marketLimits(input)} }
const grantErrors:Record<string,string>={market_amount_limit:'Choose per-swap limits within 10,000 BTC sats and 500,000 XBT sats, and total budgets at least as large as those limits.',market_grants_required:'Market pricing requires routed channels.',market_grant_mismatch:'The market limits are invalid. Check the four amount and budget fields.',
  "restored_authority_blocked": "Old grant authority is blocked after restore. Preserve existing swap records and complete the recovery setup.",
  "choose_one_connected_channel": "No eligible channel set was selected. Check connected, normal channels and any channel restriction.",
  "existing_grant_differs_or_uncertain": "The request differs from the saved grant, or its creation is unfinished. Retrieve using the original settings; replace only after existing swaps finish.",
  "previous_swap_requires_recovery": "An earlier swap still requires recovery. Check both directional histories and leave its records intact.",
  "previous_gate_not_terminal": "An earlier incoming payment gate is not terminal. Finish the existing swap before creating a new grant.",
  "previous_attempt_not_terminal": "An earlier outgoing payment is not terminal. Let that exact attempt recover before creating a new grant.",
  "previous_enrollment_unfinished": "An earlier enrollment is unfinished. Keep the controller running and check both swap histories.",
  "invalid_swap_limit": "Choose a maximum between 1 and 10 swaps."
}
async function run(effects: any, mode: string, input: object) {
  return sdk.SubContainer.withTemp(effects,{imageId:'lightning'},mainMounts,'reverse-session',async sub => {
    const res=await sub.exec(['/opt/xbt-venv/bin/python','/usr/local/libexec/reverse_session.py','xbt',rootDir,mode],{input:JSON.stringify(input)})
    let report:any
    try { report=JSON.parse(String(res.stdout)) } catch { throw new Error('Grant operation interrupted. Preserve its records and inspect before retrying.') }
    if(res.exitCode!==0)throw new Error((typeof report?.error === 'string' && Object.hasOwn(grantErrors,report.error) ? grantErrors[report.error] : '') || 'Reverse grant refused. Finish swaps in both directions; check channels, restore state and explicit XBT gate activation. Leave New grant off when recovering an interrupted setup.')
    const labels:Record<string,string>={market_limits:'Market limits (millisats)',credential:'Controller grant credential',max_swaps:'Maximum swaps',max_delay_blocks:'Maximum BTC route delay (blocks)',expires_at:'Enrollment expiry (Unix time)',restart_required:'Restart BTC coordinator required',payment_started:'Payment started',paused:'New enrollments paused',recovery_preserved:'Existing recovery preserved'}
    return {version:'1' as const,title:'XBT Reverse Swap Grant',message: mode==='pause' ? 'New enrollments stopped. Keep the controller running to finish already enrolled swaps.' : 'Save this credential under Pair XBT to BTC Grants in Swap Controller. This action does not send a payment.',
      result:{type:'group' as const,value:Object.entries(report).filter(([k])=>k in labels).map(([k,v])=>({name:labels[k],description:null,type:'single' as const,value:typeof v==='object'?JSON.stringify(v):String(v),masked:k==='credential',copyable:k==='credential',qr:false}))}}
  })
}
export const enableReverseSession=sdk.Action.withInput('enable-reverse-session',meta('Enable XBT to BTC Grant'),sdk.InputSpec.of({
  market:sdk.Value.toggle({name:'Enable Neoxa market-priced swaps',description:'A new grant is required to change pricing mode. Both coordinators must use identical limits. Market mode requires routed channels.',default:false}),
  maxBtcSats:sdk.Value.number({name:'Market: maximum BTC sats per swap (including coordinator routing)',required:true,integer:true,min:1,max:10000,default:10000,placeholder:null}),
  maxXbtSats:sdk.Value.number({name:'Market: maximum XBT sats per swap (including coordinator routing)',required:true,integer:true,min:1,max:500000,default:500000,placeholder:null}),
  totalBtcSats:sdk.Value.number({name:'Market: total BTC sat budget',description:'Every enrolled quote reserves its full amount permanently, including failed swaps.',required:true,integer:true,min:1,max:100000,default:50000,placeholder:null}),
  totalXbtSats:sdk.Value.number({name:'Market: total XBT sat budget',required:true,integer:true,min:1,max:5000000,default:2500000,placeholder:null}),
  maxSwaps:sdk.Value.number({name:'Maximum swaps (1–10)',required:true,integer:true,min:1,max:10,default:5,placeholder:null}),
  newGrant:sdk.Value.toggle({name:'Replace a previous grant with a new 24-hour budget',description:'Only after every previous enrollment has finished. Leave off to retrieve the current grant without changing its budget.',default:false}),
  confirmed:sdk.Value.toggle({name:'Authorize the selected swap pricing mode and limits: up to 10 BTC sats routing fee, 288 blocks for new grants, 4 hops, one part and attempt',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'enable',{...grantInput(input),channel:'',routed:true,maxDelay:288}))
export const pauseReverseSession=sdk.Action.withInput('pause-reverse-session',meta('Pause XBT to BTC Enrollments'),sdk.InputSpec.of({
  confirmed:sdk.Value.toggle({name:'Pause new enrollments; keep existing recovery enabled',default:false}),
}),async()=>{},async({effects,input})=>run(effects,'pause',input))
