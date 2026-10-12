"""Read the recorded group footprint and render its actual relationships."""
from __future__ import annotations
import datetime as dt
import json
import math
import re
import streamlit.components.v1 as components

def norm(value):return str(value or '').lower().replace('_',' ').strip()
def active(row):
    today=dt.date.today().isoformat()
    start=str(row.get('effective_from') or row.get('valid_from') or '')[:10]
    end=str(row.get('effective_to') or row.get('valid_to') or '')[:10]
    return (not start or start<=today) and (not end or end>=today)

def collect_network(core, root_id, max_depth=5, max_companies=150):
    root=str(root_id);members={root};depths={root:0};frontier={root};edges=[];seen_edges=set();truncated=False
    aliases={root:root}
    def add(st,source,tt,target,role,row):
        if not source or not target:return
        source=aliases.get(str(source),str(source));target=aliases.get(str(target),str(target))
        key=(st,source,tt,target,norm(role))
        if key in seen_edges:return
        seen_edges.add(key)
        edges.append(dict(source=source,target=target,source_type=st,target_type=tt,label=norm(role),
            source_url=row.get('source_url') or '',source_id=row.get('evidence_source_id') or row.get('source_id'),
            confidence=row.get('confidence') or row.get('role_status') or '',metadata=row.get('metadata') or {}))
    for depth in range(max_depth):
        if not frontier:break
        lookup=set(frontier)
        for eid in sorted(frontier):
            for alias in core._entity_identity_bundle(eid).get('ids') or [eid]:aliases[str(alias)]=eid;lookup.add(str(alias))
        values=tuple(sorted(lookup));next_members=set()
        for row in core._rows_matching_ids('pc_company_relationships','parent_company_key',values):
            if not active(row):continue
            parent=aliases.get(str(row.get('parent_company_key')),str(row.get('parent_company_key') or ''))
            child=str(row.get('child_company_key') or '');role=norm(row.get('relationship'))
            if not child or any(t in role for t in ('proposed','agreed to acquire','intends','formerly')):continue
            if not any(t in role for t in ('equity','own','subsidiary','control','business unit','joint venture','parent','portfolio')):continue
            add('entity',parent,'entity',child,role,row)
            if child not in members:next_members.add(child);depths[child]=depth+1
        for row in core._rows_matching_ids('pc_relationships','source_id',values):
            if not active(row):continue
            st=norm(row.get('source_type'));tt=norm(row.get('target_type'));role=norm(row.get('relationship_type'))
            if st!='entity':continue
            add(st,row.get('source_id'),tt,row.get('target_id'),role,row)
            if tt=='entity' and not any(t in role for t in ('owned by','proposed','agreed','intends','majority owned')) and any(t in role for t in ('owns','equity owner','subsidiary','business unit','controlled interest','parent company')):
                child=str(row.get('target_id') or '')
                if child and child not in members:next_members.add(child);depths[child]=depth+1
        room=max_companies-len(members)
        if len(next_members)>room:truncated=True
        frontier=set(sorted(next_members)[:max(0,room)]);members.update(frontier)
    if frontier:truncated=True
    lookup=set(members)
    for eid in sorted(members):
        for alias in core._entity_identity_bundle(eid).get('ids') or [eid]:aliases[str(alias)]=eid;lookup.add(str(alias))
    values=tuple(sorted(lookup))
    for row in core._rows_matching_ids('pc_company_asset_roles','entity_id',values):
        if not active(row):continue
        for field,typ in [('asset_id','asset'),('mobile_asset_id','mobile_asset')]:
            add('entity',row.get('entity_id'),typ,row.get(field),row.get('asset_role'),row)
    # Direct owner/operator columns and graph edges supplement specialist role records.
    for table,pk,typ in [('pc_assets','asset_id','asset'),('pc_mobile_assets','mobile_asset_id','mobile_asset')]:
        for field,role in [('operator_entity_id','operator'),('owner_entity_id','owner'),('manager_entity_id','manager')] if typ=='mobile_asset' else [('operator_entity_id','operator'),('owner_entity_id','owner')]:
            for row in core._rows_matching_ids(table,field,values):add('entity',row.get(field),typ,row.get(pk),role,row)
    # Read all direct graph links for final-level subsidiaries too.
    for row in core._rows_matching_ids('pc_relationships','source_id',values):
        if norm(row.get('source_type'))=='entity' and active(row):add('entity',row.get('source_id'),norm(row.get('target_type')),row.get('target_id'),row.get('relationship_type'),row)
    wanted={'entity':set(members),'asset':set(),'mobile_asset':set(),'corridor':set()}
    for e in edges:
        for side in ['source','target']:
            typ=e[side+'_type'];typ='mobile_asset' if typ=='vessel' else typ;e[side+'_type']=typ
            if typ in wanted:wanted[typ].add(e[side])
    records={};nodes=[]
    for typ,table,pk in [('entity','pc_entities','entity_id'),('asset','pc_assets','asset_id'),('mobile_asset','pc_mobile_assets','mobile_asset_id')]:
        ids=tuple(sorted(wanted[typ]))
        for row in core._rows_matching_ids(table,pk,ids):
            oid=str(row.get(pk));meta=row.get('metadata') or {};canon=meta.get('canonicalization') or {}
            if typ=='asset' and canon.get('action')=='merged_alias':continue
            records[(typ,oid)]=row
            nodes.append(dict(id=oid,type=typ,name=row.get('name') or 'Name unavailable',depth=depths.get(oid,2),
                subtype=row.get('subtype') or row.get('entity_type') or row.get('asset_type') or '',country=row.get('country') or row.get('hq_country') or ''))
    allowed={n['id'] for n in nodes};edges=[e for e in edges if e['source'] in allowed and e['target'] in allowed]
    return dict(nodes=nodes,edges=edges,records=records,members=members,depths=depths,truncated=truncated)

def render_graph(nodes, edges, root_id, height=680):
    """Canvas in an iframe avoids SVG sanitization and supports zoom, pan and node dragging."""
    data=json.dumps(dict(nodes=nodes,edges=edges,root=str(root_id)),default=str).replace('<','\\u003c')
    page=r'''<!doctype html><html><head><meta charset="utf-8"><style>
    body{margin:0;font:14px Arial;color:#25364c;background:#f8fafc}#bar{display:flex;gap:14px;align-items:center;padding:12px;background:white;border-bottom:1px solid #dce4ed}button{background:white;border:1px solid #c4d0dc;border-radius:5px;padding:6px 12px;cursor:pointer}canvas{display:block;width:100%;height:590px;cursor:grab}#detail{padding:10px 14px;background:white;min-height:20px;border-top:1px solid #dce4ed}span{font-size:12px}a{color:#276e91}</style></head><body>
    <div id="bar"><button id="reset">Fit network</button><span>Gold: companies · Green: infrastructure · Blue: vessels</span><span>Scroll to zoom · Drag background to pan · Drag a node to move it</span></div><canvas id="map"></canvas><div id="detail">Select a node to see its connections. Use the selector below to open its dossier.</div><script>
    const D=__DATA__,canvas=document.getElementById('map'),ctx=canvas.getContext('2d'),info=document.getElementById('detail');
    let w=canvas.clientWidth,h=590,scale=.75,pan={x:0,y:0},drag=null,last=null,selected=null;
    canvas.width=w*devicePixelRatio;canvas.height=h*devicePixelRatio;ctx.scale(devicePixelRatio,devicePixelRatio);
    const peers=D.nodes.filter(n=>n.id!==D.root), byId=new Map();
    D.nodes.forEach(n=>{let i=peers.indexOf(n),r=170+Math.min(n.depth||1,5)*100;n.x=n.id===D.root?0:r*Math.cos(i*2*Math.PI/Math.max(peers.length,1));n.y=n.id===D.root?0:r*Math.sin(i*2*Math.PI/Math.max(peers.length,1));n.vx=0;n.vy=0;byId.set(n.id,n)});
    let links=D.edges.map(e=>({...e,a:byId.get(e.source),b:byId.get(e.target)})).filter(e=>e.a&&e.b);
    function fit(){let extent=Math.max(350,...D.nodes.map(n=>Math.max(Math.abs(n.x),Math.abs(n.y))+110));scale=Math.min(w,h)/(extent*2);pan={x:0,y:0};draw()}
    function draw(){ctx.clearRect(0,0,w,h);ctx.save();ctx.translate(w/2+pan.x,h/2+pan.y);ctx.scale(scale,scale);
      links.forEach(e=>{let emphasis=selected&&(e.source===selected.id||e.target===selected.id);ctx.beginPath();ctx.moveTo(e.a.x,e.a.y);ctx.lineTo(e.b.x,e.b.y);ctx.strokeStyle=emphasis?'#276e91':'#a7b7c8';ctx.lineWidth=emphasis?3:1.4;ctx.globalAlpha=selected?(emphasis?1:.2):.65;ctx.stroke();if(emphasis){ctx.fillStyle='#26394b';ctx.font='12px Arial';ctx.fillText(e.label||'',(e.a.x+e.b.x)/2,(e.a.y+e.b.y)/2)}});
      ctx.globalAlpha=1;D.nodes.forEach(n=>{let root=n.id===D.root,r=root?26:16;ctx.beginPath();ctx.arc(n.x,n.y,r,0,Math.PI*2);ctx.fillStyle=n.type==='entity'?'#d7b56d':n.type==='mobile_asset'?'#6babc4':'#78b79a';ctx.fill();ctx.strokeStyle=selected===n?'#112d49':'#fff';ctx.lineWidth=selected===n?4:2;ctx.stroke();ctx.fillStyle='#20374f';ctx.font=(root?'bold 15':'12')+'px Arial';ctx.textAlign='center';const name=n.name||'';ctx.fillText(name.length>30?name.slice(0,29)+'…':name,n.x,n.y+r+16)});ctx.restore()}
    function world(e){let box=canvas.getBoundingClientRect();return{x:(e.clientX-box.left-w/2-pan.x)/scale,y:(e.clientY-box.top-h/2-pan.y)/scale}}
    canvas.onpointerdown=e=>{let p=world(e);drag=D.nodes.find(n=>Math.hypot(n.x-p.x,n.y-p.y)<28);last={x:e.clientX,y:e.clientY};canvas.setPointerCapture(e.pointerId);if(drag){selected=drag;let rel=links.filter(l=>l.source===drag.id||l.target===drag.id);info.textContent=drag.name+' — '+(drag.type==='entity'?'Company':drag.type==='mobile_asset'?'Vessel':'Infrastructure')+' · '+rel.length+' displayed connections';}draw()};
    canvas.onpointermove=e=>{if(!last)return;if(drag){let p=world(e);drag.x=p.x;drag.y=p.y;drag.pinned=true}else{pan.x+=e.clientX-last.x;pan.y+=e.clientY-last.y}last={x:e.clientX,y:e.clientY};draw()};canvas.onpointerup=()=>{drag=null;last=null};
    canvas.onwheel=e=>{e.preventDefault();scale=Math.max(.12,Math.min(3,scale*Math.exp(-e.deltaY*.001)));draw()};
    document.getElementById('reset').onclick=fit;
    for(let tick=0;tick<130;tick++){for(let i=0;i<D.nodes.length;i++)for(let j=i+1;j<D.nodes.length;j++){let a=D.nodes[i],b=D.nodes[j],dx=b.x-a.x,dy=b.y-a.y,d2=Math.max(100,dx*dx+dy*dy),f=2400/d2;a.vx-=dx*f;a.vy-=dy*f;b.vx+=dx*f;b.vy+=dy*f}links.forEach(e=>{let dx=e.b.x-e.a.x,dy=e.b.y-e.a.y,d=Math.max(1,Math.hypot(dx,dy)),f=(d-150)*.008;e.a.vx+=dx/d*f;e.a.vy+=dy/d*f;e.b.vx-=dx/d*f;e.b.vy-=dy/d*f});D.nodes.forEach(n=>{if(n.id===D.root){n.x=0;n.y=0;n.vx=n.vy=0;return}n.vx*=.72;n.vy*=.72;n.x+=n.vx;n.y+=n.vy})}fit();
    </script></body></html>'''.replace('__DATA__',data)
    components.html(page,height=height,scrolling=False)
