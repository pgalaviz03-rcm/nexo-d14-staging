/* Project account dashboard. Counters come only from stored snapshots. */
window.NexoNetworks={install({api,byId,getProject,onConfigure}){
 let sequence=0,packet=null,actor=0,account='',cut=null,dirty=false,loadingImport=false;
 const names={facebook:'Facebook',instagram:'Instagram',x:'X',tiktok:'TikTok',youtube:'YouTube',press:'Prensa',other:'Sitio público'};
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const number=x=>x===null||x===undefined?'—':Number(x).toLocaleString('es-MX',{maximumFractionDigits:1});
 const date=x=>x?new Date(x).toLocaleString('es-MX',{dateStyle:'medium',timeStyle:'short'}):'—';
 const message=t=>{byId('networksStatus').textContent=t;};
 const path=()=>'/api/projects/'+getProject()+'/networks';
 function range(){if(cut)return cut;const days=byId('networksPeriod').value;let end=new Date(),start;
  if(days==='custom'){if(!byId('networksFrom').value||!byId('networksTo').value)throw Error('Completa las fechas del periodo.');
   start=new Date(byId('networksFrom').value+'T00:00:00');end=new Date(byId('networksTo').value+'T00:00:00');end.setDate(end.getDate()+1);end=new Date(Math.min(end.getTime(),Date.now()));
  }else{end.setHours(0,0,0,0);start=new Date(end);start.setDate(start.getDate()-Number(days));}
  return {start:start.toISOString(),end:end.toISOString()};
 }
 function clear(){packet=null;for(const id of ['networksFollowers','networksInteractions','networksViews','networksReach'])byId(id).textContent='—';
  for(const id of ['networksFollowerDelta','networksInteractionDelta','networksScope','networksPeriodLabel','networksChartNote','networksCoverage'])byId(id).textContent='';
  for(const id of ['networksContent','networksChart','networksComparison','networksBreakdown'])byId(id).replaceChildren();byId('networksExport').disabled=true;byId('networksTemplate').disabled=true;byId('networksImportPanel').hidden=true;}
 function download(value,name){const url=URL.createObjectURL(new Blob([JSON.stringify(value,null,2)],{type:'application/json'})),a=el('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
 function drawChart(series){const root=byId('networksChart');root.replaceChildren();const points=series.filter(p=>p.followers!==null&&Number.isFinite(p.followers)&&Number.isFinite(new Date(p.at).getTime()));
  if(!points.length){root.append(el('p','La evolución aparecerá con las primeras capturas de esta cuenta.','network-chart-empty'));return;}
  const svg=(tag,attrs={},text)=>{const node=document.createElementNS('http://www.w3.org/2000/svg',tag);for(const [k,v] of Object.entries(attrs))node.setAttribute(k,String(v));if(text!==undefined)node.textContent=text;return node;};
  const graph=svg('svg',{viewBox:'0 0 640 210',role:'img','aria-label':'Seguidores en las capturas observadas del periodo'});
  const vals=points.map(p=>p.followers),lo=Math.min(...vals),hi=Math.max(...vals),padding=Math.max(1,(hi-lo)*.15),floor=Math.max(0,lo-padding),ceil=hi+padding;
  const first=new Date(points[0].at).getTime(),last=new Date(points.at(-1).at).getTime();
  const x=p=>last===first?345:60+545*(new Date(p.at).getTime()-first)/(last-first),y=p=>165-130*(p.followers-floor)/(ceil-floor);
  for(const v of [floor,(floor+ceil)/2,ceil]){const py=165-130*(v-floor)/(ceil-floor);graph.append(svg('line',{x1:60,x2:615,y1:py,y2:py,stroke:'#e7ecf5'}),svg('text',{x:4,y:py+4,fill:'#78859b','font-size':11},number(v)));}
  if(points.length>1)graph.append(svg('polyline',{points:points.map(p=>x(p)+','+y(p)).join(' '),fill:'none',stroke:'#7560db','stroke-width':3}));
  for(const p of points){const dot=svg('circle',{cx:x(p),cy:y(p),r:4.5,fill:'#7560db',stroke:'#fff','stroke-width':2});dot.append(svg('title',{},number(p.followers)+' · '+date(p.at)));graph.append(dot);}
  root.append(graph);byId('networksChartNote').textContent=points.length+' capturas observadas · '+date(points[0].at)+' a '+date(points.at(-1).at);
 }
 function render(p){packet=p;actor=p.selected_actor_id||0;account=p.selected_account?.url||'';cut=p.window;
  const select=byId('networksActor');select.replaceChildren();for(const a of p.actors){const o=el('option',a.name+(a.kind==='primary'?' · principal':''));o.value=a.id;select.append(o);}select.value=String(actor);
  const selected=p.selected_account;byId('networksScope').textContent=selected?(names[selected.network]||selected.network)+' · '+selected.actor_name:'Selecciona las cuentas públicas de este proyecto.';
  byId('networksPeriodLabel').textContent='Actividad del '+date(p.window.start)+' al '+date(p.window.end)+' · comparación con el periodo anterior de igual duración';
  byId('networksImportPanel').hidden=!p.can_import;byId('networksExport').disabled=false;byId('networksTemplate').disabled=!p.can_import||!selected;
  if(selected){byId('networksFollowers').textContent=number(selected.followers);byId('networksInteractions').textContent=number(selected.current.interactions);byId('networksViews').textContent=number(selected.current.views);byId('networksReach').textContent=number(selected.current.reach);
   const delta=selected.followers_change.absolute;byId('networksFollowerDelta').textContent='Observación: '+date(selected.followers_as_of)+(delta===null?'':' · '+(delta>0?'+':'')+number(delta)+' entre capturas desde '+date(selected.followers_baseline_at));
   const change=selected.changes.interactions;byId('networksInteractionDelta').textContent=change.absolute===null?'Actividad del periodo declarado':(change.absolute>0?'+':'')+number(change.absolute)+' frente al periodo anterior'+(change.percent===null?'':' · '+number(change.percent)+'%');
   drawChart(selected.series);
   for(const [label,v] of [['Publicaciones del periodo',selected.current.posts],['Impresiones del periodo',selected.current.impressions],['Interacciones por 100 seguidores',selected.interactions_per_100_followers]]){const row=el('div',undefined,'network-metric-row');row.append(el('span',label),el('b',number(v)));byId('networksBreakdown').append(row);}
   if(selected.activity_captured_at)byId('networksBreakdown').append(el('p','Captura de actividad: '+date(selected.activity_captured_at),'note'));
   if(selected.ratio_followers_as_of)byId('networksBreakdown').append(el('p','Seguidores usados en el cálculo: observación del '+date(selected.ratio_followers_as_of),'note'));
  }else drawChart([]);
  const root=byId('networksContent');for(const row of p.accounts){const card=el('button',undefined,'network-account-card'+(row.url===account?' selected':''));card.type='button';card.setAttribute('aria-pressed',String(row.url===account));
   card.append(el('span',names[row.network]||row.network,'eyebrow'),el('strong',number(row.followers)),el('span','seguidores','note'),el('small',row.url),
    el('small',row.status==='no_captures'?'Primera captura pendiente':'Última observación: '+date(row.followers_as_of)));
   card.onclick=()=>{account=row.url;reload();};root.append(card);}
  if(!p.accounts.length)root.append(el('p','Añade las referencias de este actor desde Actores para comenzar.','live-empty'));
  const comparison=byId('networksComparison');const table=el('table',undefined,'network-table'),head=el('tr');for(const t of ['Actor · cuenta de '+(names[p.comparison_network]||p.comparison_network),'Seguidores · última captura','Publicaciones','Interacciones','Vistas'])head.append(el('th',t));
  const thead=el('thead');thead.append(head);table.append(thead);const tbody=el('tbody');
  for(const row of p.comparison){const tr=el('tr'),who=el('td');who.append(el('b',row.actor_name));if(row.account){const link=el('a',row.account.url);if(/^https:\/\//i.test(row.account.url)){link.href=row.account.url;link.target='_blank';link.rel='noopener noreferrer';}who.append(link);}
   who.setAttribute('data-label','Actor y cuenta');tr.append(who);const followers=el('td',number(row.account?.followers));followers.setAttribute('data-label','Seguidores');if(row.account?.followers_as_of)followers.append(el('small',date(row.account.followers_as_of)));tr.append(followers);
   for(const [label,v] of [['Publicaciones',row.account?.current.posts],['Interacciones',row.account?.current.interactions],['Vistas',row.account?.current.views]]){const cell=el('td',number(v));cell.setAttribute('data-label',label);tr.append(cell);}tbody.append(tr);}
  table.append(tbody);comparison.append(table);if(!p.comparison.length)comparison.append(el('p','Sin actores activos en este proyecto.','note'));
  byId('networksCoverage').textContent=p.coverage_bounded?'Consulta acotada a las últimas '+p.query_limit_per_actor+' capturas y '+p.accounts_limit_per_actor+' cuentas por actor.':'Una cuenta por actor en la misma red. Los guiones indican que falta una captura comparable; no equivalen a cero.';
 }
 async function reload(){if(!getProject())return;const stamp=++sequence,pid=getProject();clear();message('Preparando el corte de las cuentas…');
  try{const r=range();const q=new URLSearchParams({start:r.start,end:r.end,actor_id:actor,network:byId('networksNetwork').value,account_url:account});
   const p=await api(path()+'?'+q);if(stamp!==sequence||pid!==getProject())return;message('');render(p);
  }catch(e){if(stamp===sequence&&pid===getProject())message(e.message);}
 }
 byId('networksActor').onchange=()=>{actor=Number(byId('networksActor').value);account='';reload();};
 byId('networksNetwork').onchange=()=>{account='';reload();};
 byId('networksPeriod').onchange=()=>{cut=null;byId('networksDates').hidden=byId('networksPeriod').value!=='custom';if(byId('networksPeriod').value!=='custom')reload();else{sequence++;clear();}};
 for(const id of ['networksFrom','networksTo'])byId(id).onchange=()=>{sequence++;cut=null;clear();};
 byId('networksRefresh').onclick=()=>{cut=null;reload();};byId('networksConfigure').onclick=()=>onConfigure();
 byId('networksExport').onclick=()=>{if(packet)download(packet,'NEXO_Redes_Corte.json');};
 byId('networksTemplate').onclick=()=>{if(!packet?.can_import||!packet.selected_account)return;const a=packet.selected_account;
  download({provider:'manual',items:[{actor_id:a.actor_id,network:a.network,url:a.url,captured_at:new Date().toISOString(),metrics_from:packet.window.start,metrics_to:packet.window.end,
   followers:null,posts:null,views:null,impressions:null,reach:null,interactions:null}]},'NEXO_Redes_Plantilla.json');};
 byId('networksFile').onchange=()=>{dirty=!!byId('networksFile').files.length;};
 byId('networksImportForm').onsubmit=async e=>{e.preventDefault();if(loadingImport||!packet?.can_import)return;const file=byId('networksFile').files[0];if(!file)return;
  if(file.size>1_000_000){byId('networksImportStatus').textContent='Máximo 1 MB por archivo.';return;}
  const pid=getProject(),stamp=sequence;loadingImport=true;byId('networksImport').disabled=true;
  try{const body=JSON.parse(await file.text());if(pid!==getProject()||stamp!==sequence)return;
   const result=await api(path()+'/captures',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
   if(pid!==getProject())return;dirty=false;byId('networksFile').value='';await reload();byId('networksImportStatus').textContent=result.inserted+' capturas incorporadas · '+result.duplicates+' ya existentes.';
  }catch(e){if(pid===getProject())byId('networksImportStatus').textContent=e instanceof SyntaxError?'El archivo no es un JSON válido.':e.message==='Error de consulta 422'?'Revisa las fechas, los periodos y los contadores numéricos del archivo.':e.message;}finally{loadingImport=false;byId('networksImport').disabled=false;}
 };
 function resetProject(){sequence++;actor=0;account='';cut=null;dirty=false;clear();byId('networksActor').replaceChildren();byId('networksNetwork').value='all';byId('networksPeriod').value='7';byId('networksDates').hidden=true;
  byId('networksFrom').value='';byId('networksTo').value='';byId('networksFile').value='';byId('networksImportPanel').hidden=true;byId('networksImportPanel').open=false;byId('networksImportStatus').textContent='';message('');}
 return {focusActor:id=>{actor=Number(id)||0;account='';cut=null;byId('networksNetwork').value='all';byId('networksPeriod').value='7';byId('networksDates').hidden=true;return reload();},reload,resetProject,canLeaveProject:()=>!loadingImport&&(!dirty||confirm('Hay un archivo de capturas sin incorporar. ¿Descartarlo al cambiar de proyecto?'))};
}};
