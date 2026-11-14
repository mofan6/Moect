"use client"

import * as React from "react"
import { cn } from "@/lib/utils"
import {call} from '@/src/native'

// Shared native-resolution promises prevent repeat requests on page switches.
const resolvedAvatars=new Map<string,Promise<string>>()
function resolveAvatar(src:string){
  if(!/^(?:https?:|moect-avatar:)/i.test(src))return Promise.resolve(src)
  if(!resolvedAvatars.has(src)){
    if(resolvedAvatars.size>=128)resolvedAvatars.delete(resolvedAvatars.keys().next().value!)
    resolvedAvatars.set(src,call('avatar',{url:src}).then(r=>r.url||'').catch(()=>''))
  }
  const pending=resolvedAvatars.get(src)!;resolvedAvatars.delete(src);resolvedAvatars.set(src,pending)
  return pending
}

interface AvatarContextValue {
  imageLoaded: boolean
  setImageLoaded: (loaded: boolean) => void
  element: React.RefObject<HTMLDivElement|null>
}

const AvatarContext = React.createContext<AvatarContextValue>({
  imageLoaded: false,
  setImageLoaded: () => {},
  element: {current:null},
})

const Avatar = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const [imageLoaded, setImageLoaded] = React.useState(false)
  const element=React.useRef<HTMLDivElement>(null)
  
  return (
    <AvatarContext.Provider value={{ imageLoaded, setImageLoaded,element }}>
      <div
        ref={node=>{element.current=node;if(typeof ref==='function')ref(node);else if(ref)ref.current=node}}
        className={cn(
          "relative flex h-10 w-10 shrink-0 overflow-hidden rounded-full",
          className
        )}
        {...props}
      />
    </AvatarContext.Provider>
  )
})
Avatar.displayName = "Avatar"

const AvatarImage = React.forwardRef<
  HTMLImageElement,
  React.ImgHTMLAttributes<HTMLImageElement>
>(({ className, onLoad, onError, src, ...props }, ref) => {
  const { setImageLoaded,element } = React.useContext(AvatarContext)
  const [localSrc,setLocalSrc]=React.useState('')
  React.useEffect(()=>{
    let current=true
    setLocalSrc('');setImageLoaded(false)
    const start=()=>{if(src&&current)resolveAvatar(src).then(url=>{if(current)setLocalSrc(url)})}
    let observer:IntersectionObserver|undefined
    if(src&&/^(?:https?:|moect-avatar:)/i.test(src)&&element.current){
      observer=new IntersectionObserver(entries=>{if(entries.some(entry=>entry.isIntersecting)){observer?.disconnect();start()}},{rootMargin:'120px'})
      observer.observe(element.current)
    }else start()
    return()=>{current=false;observer?.disconnect()}
  },[src])
  if(!localSrc)return null
  
  return (
    <img
      ref={ref}
      src={localSrc}
      className={cn("aspect-square h-full w-full object-cover", className)}
      onLoad={(e) => {
        setImageLoaded(true)
        onLoad?.(e)
      }}
      onError={(e) => {
        setImageLoaded(false)
        onError?.(e)
      }}
      {...props}
    />
  )
})
AvatarImage.displayName = "AvatarImage"

const AvatarFallback = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const { imageLoaded } = React.useContext(AvatarContext)
  
  if (imageLoaded) return null
  
  return (
    <div
      ref={ref}
      className={cn(
        "absolute inset-0 flex h-full w-full items-center justify-center rounded-full bg-neutral-100 dark:bg-neutral-700 text-neutral-600 dark:text-neutral-300",
        className
      )}
      {...props}
    />
  )
})
AvatarFallback.displayName = "AvatarFallback"

export { Avatar, AvatarImage, AvatarFallback }
