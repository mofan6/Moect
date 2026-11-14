declare global {interface Window {QWebChannel:any; qt:any; pywebview:any; __wceNativeRegions?:boolean; __ready?:boolean; __wce?:any}}
let sequence=0
const pending=new Map<string,{resolve:(value:any)=>void,reject:(e:Error)=>void}>()
let bridge:any
export const ready=new Promise<void>(resolve=>{
  const edge=()=>{if(window.pywebview?.api?.invoke){bridge=window.pywebview.api;resolve();return true}return false}
  if(edge())return
  window.addEventListener('pywebviewready',edge,{once:true})
  if(window.qt){
    const script=document.createElement('script');script.src='qrc:///qtwebchannel/qwebchannel.js'
    script.onload=()=>new window.QWebChannel(window.qt.webChannelTransport,(channel:any)=>{
      bridge=channel.objects.native
      bridge.windowState.connect((maximized:boolean)=>window.dispatchEvent(new CustomEvent('wce-window-state',{detail:{maximized}})))
      bridge.response.connect((raw:string)=>{const data=JSON.parse(raw),p=pending.get(data.id);if(!p)return;pending.delete(data.id);data.error?p.reject(new Error(data.error)):p.resolve(data.result)})
      resolve()
    });document.head.append(script)
  }
})
// Limit requests before pywebview creates a native thread for each invocation.
// Two avatar slots leave capacity for state, messages and window interactions.
const calls:{action:string;run:()=>Promise<any>;resolve:(value:any)=>void;reject:(error:any)=>void}[]=[]
let activeCalls=0,activeAvatars=0
function drain(){
 while(activeCalls<6){
  const index=calls.findIndex(item=>item.action!=='avatar'||activeAvatars<2)
  if(index<0)return
  const item=calls.splice(index,1)[0],avatar=item.action==='avatar'
  activeCalls++;if(avatar)activeAvatars++
  Promise.resolve().then(item.run).then(item.resolve,item.reject).finally(()=>{activeCalls--;if(avatar)activeAvatars--;drain()})
 }
}
async function invoke(action:string,payload:any){
 if(bridge.invoke){const data=await bridge.invoke(action,payload);if(data.error)throw new Error(data.error);return data.result}
 return new Promise<any>((resolve,reject)=>{const id=String(++sequence);pending.set(id,{resolve,reject});bridge.request(JSON.stringify({id,action,payload}))})
}
export async function call(action:string,payload:any={}){
 await ready
 return new Promise<any>((resolve,reject)=>{
  const item={action,run:()=>invoke(action,payload),resolve,reject}
  if(action.startsWith('window_'))calls.unshift(item);else calls.push(item)
  drain()
 })
}
export async function nativeFetch(_url:string,options:any):Promise<any>{
  const payload=JSON.parse(options.body)
  const data=await call('qce_preview',payload)
  return {ok:true,status:200,json:async()=>({success:true,data})}
}
