'use client';

import { useEffect, useMemo, useRef, useState } from 'react';

type Incident = { layer:'Piracy'|'Conflict'; id:string; vessel:string; date:string; theatre:string; category:string; outcome:string; location:string; source:string; lat:number; lon:number; precision:'reported position'|'regional reference only' };
const incidents:Incident[]=[
  {layer:'Conflict',id:'UKMTO-053-26',vessel:'Unnamed container vessel',date:'2026-10-07',theatre:'Red Sea / Bab el-Mandeb',category:'Armed attack',outcome:'Reported fired upon',location:"12°58.77′N 43°12.54′E",source:'IMB incident 053-26 — verify primary report before operational use',lat:12+58.77/60,lon:43+12.54/60,precision:'reported position'},
  {layer:'Piracy',id:'PIR-2026-62',vessel:'HONOUR 25',date:'2026-04-21',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'Near Xaafuun / Mareeyo, Puntland',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief',lat:10.43,lon:51.13,precision:'regional reference only'},
  {layer:'Piracy',id:'PIR-2026-63',vessel:'SWARD',date:'2026-04-26',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'Near Garacad, Puntland',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief',lat:6.95,lon:49.32,precision:'regional reference only'},
  {layer:'Piracy',id:'PIR-2026-64',vessel:'EUREKA',date:'2026-05-04',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'Yemen–Somalia corridor',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief',lat:12.0,lon:48.0,precision:'regional reference only'},
  {layer:'Piracy',id:'PIR-2026-65',vessel:'ASANA',date:'2026-07-17',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'South of Al Mukalla',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief and UKMTO warning 090-26',lat:13.1,lon:49.1,precision:'regional reference only'},
  {layer:'Piracy',id:'PIR-2026-66',vessel:'LUTUF',date:'2026-08-17',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'Approximately 4 NM south of Maraya',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief and UKMTO warning 114-26',lat:9.7,lon:50.6,precision:'regional reference only'},
  {layer:'Piracy',id:'PIR-2026-67',vessel:'SEAMULL (SIBU 1)',date:'2026-08-20',theatre:'Somalia / Gulf of Aden',category:'Hijacking',outcome:'Reported hijacked',location:'Gulf of Aden',source:'Existing P&C data/piracy_2026.csv; German Navy Shipping Centre brief',lat:12.25,lon:47.8,precision:'regional reference only'}
];
const regions=['All regions','Somalia / Gulf of Aden','Red Sea / Bab el-Mandeb'] as const;
const layers=['All Events','Piracy','Conflict'] as const;
type LeafletMap={remove:()=>void;fitBounds:(bounds:number[][],opts?:object)=>void;setView:(point:number[],zoom:number)=>void};
type LeafletGlobal={map:(el:HTMLElement,opts:object)=>LeafletMap;tileLayer:(url:string,opts:object)=>{addTo:(map:LeafletMap)=>void};circleMarker:(point:number[],opts:object)=>{addTo:(map:LeafletMap)=>{on:(event:string,fn:()=>void)=>void;bindTooltip:(text:string)=>void}}};
declare global {interface Window {L?:LeafletGlobal}}
export default function PiracyMap(){
 const host=useRef<HTMLDivElement>(null),instance=useRef<LeafletMap|null>(null);
 const [layer,setLayer]=useState<string>('All Events'),[region,setRegion]=useState<string>('All regions'),[selected,setSelected]=useState<string>('UKMTO-053-26'),[ready,setReady]=useState(false),[mapError,setMapError]=useState(false);
 const visible=useMemo(()=>incidents.filter(x=>(layer==='All Events'||x.layer===layer)&&(region==='All regions'||x.theatre===region)),[region,layer]);
 const detail=visible.find(x=>x.id===selected) || visible[0];
 useEffect(()=>{
  const cssId='btw-leaflet-css';if(!document.getElementById(cssId)){const link=document.createElement('link');link.id=cssId;link.rel='stylesheet';link.href='https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';document.head.appendChild(link)}
  if(window.L){setReady(true);return}
  const existing=document.getElementById('btw-leaflet-script') as HTMLScriptElement|null;
  const script=existing||document.createElement('script');
  const onLoad=()=>setReady(true),onError=()=>setMapError(true);
  script.addEventListener('load',onLoad);script.addEventListener('error',onError);
  if(!existing){script.id='btw-leaflet-script';script.src='https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';script.async=true;document.body.appendChild(script)}
  return ()=>{script.removeEventListener('load',onLoad);script.removeEventListener('error',onError)}
 },[]);
 useEffect(()=>{
  if(!ready||!window.L||!host.current)return;
  const L=window.L;
  instance.current?.remove();
  const map=L.map(host.current,{zoomControl:true,scrollWheelZoom:false}).setView([12,51],5);
  instance.current=map;
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png',{attribution:'&copy; OpenStreetMap &copy; CARTO',maxZoom:18}).addTo(map);
  visible.forEach(item=>{
   const exact=item.precision==='reported position';
   const marker=L.circleMarker([item.lat,item.lon],{radius:exact?9:12,color:exact?'#f3b35b':'#77b7d3',fillColor:exact?'#f3b35b':'#35627b',fillOpacity:exact?.9:.45,weight:exact?2:1,dashArray:exact?undefined:'4 4'}).addTo(map);
   marker.bindTooltip(item.vessel+' · '+(exact?'reported position':'regional reference'));
   marker.on('click',()=>setSelected(item.id));
  });
  if(visible.length)map.fitBounds(visible.map(x=>[x.lat,x.lon]),{padding:[45,45],maxZoom:7});
  return ()=>{map.remove();instance.current=null};
 },[ready,visible]);
 return <div style={{display:'grid',gap:20}}>
  <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>{layers.map(l=><button type="button" key={l} onClick={()=>{setLayer(l);setRegion('All regions');setSelected('')}} style={{cursor:'pointer',border:'1px solid #406078',borderRadius:999,background:layer===l?'#ccab62':'#10243a',color:layer===l?'#091627':'#edf4fb',padding:'11px 20px',fontWeight:800}}>{l}</button>)}</div>
  <p style={{margin:0}}>Select a security layer, then a region. All Events combines the piracy and conflict layers; it does not represent every event in the wider P&C database yet.</p>
  <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>{regions.map(r=><button type="button" key={r} onClick={()=>{setRegion(r);setSelected('')}} style={{cursor:'pointer',border:'1px solid #406078',borderRadius:999,background:region===r?'#ccab62':'#10243a',color:region===r?'#091627':'#edf4fb',padding:'9px 14px',fontWeight:700}}>{r}</button>)}</div>
  <div style={{display:'grid',gridTemplateColumns:'minmax(0, 2fr) minmax(280px, 1fr)',gap:16}}>
   <div style={{minWidth:0,position:'relative',border:'1px solid #29455e',borderRadius:12,overflow:'hidden',background:'#132d45'}}>
    <div ref={host} role="application" aria-label="Interactive maritime security incident map" style={{height:520,width:'100%',zIndex:0}}/>
    {!ready&&<div style={{position:'absolute',top:16,left:16,background:'#10243a',padding:12,borderRadius:8}}>{mapError?'Map tiles unavailable; incident list remains accessible.':'Loading incident map…'}</div>}
    <div style={{position:'absolute',bottom:10,left:10,zIndex:500,background:'#10243aee',padding:'8px 12px',borderRadius:7,fontSize:12}}>🟠 Reported position &nbsp; ◯ Regional reference (not event coordinates)</div>
   </div>
   <aside style={{background:'#10243a',border:'1px solid #29455e',borderRadius:12,padding:20,minWidth:0}}>
    <div className="eyebrow">Incident dossier</div>
    {detail&&<><h2 style={{marginTop:12}}>{detail.vessel}</h2><p style={{color:'#edf4fb'}}>{detail.outcome}</p><dl style={{display:'grid',gridTemplateColumns:'100px 1fr',gap:'10px 8px',fontSize:13}}>{[['Incident date',detail.date],['Theatre',detail.theatre],['Classification',detail.category],['Location',detail.location],['Map accuracy',detail.precision],['Source',detail.source]].map(([label,value])=><div key={label} style={{display:'contents'}}><dt style={{color:'#9fb7cb'}}>{label}</dt><dd style={{margin:0,overflowWrap:'anywhere'}}>{value}</dd></div>)}</dl></>}
    <p style={{fontSize:12}}>Pilot entries from the existing 2026 research CSV, plus one positioned incident. These are not yet a live Supabase feed. Source claims and ongoing status require reconciliation.</p>
   </aside>
  </div>
  <section><h2>Incident list <span style={{color:'#a9bdd0',fontSize:15}}>({visible.length} pilot records)</span></h2><div style={{display:'grid',gap:8}}>{visible.map(x=><button type="button" key={x.id} onClick={()=>setSelected(x.id)} style={{textAlign:'left',cursor:'pointer',padding:14,border:'1px solid '+(detail?.id===x.id?'#ccab62':'#29455e'),borderRadius:8,background:'#10243a',color:'#edf4fb'}}><strong>{x.vessel}</strong><span style={{display:'block',color:'#a9bdd0',fontSize:13}}>{x.date} · {x.layer} · {x.category} · {x.location} · {x.precision}</span></button>)}</div></section>
 </div>;
}
