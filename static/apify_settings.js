/* Owner form component. Plans are independent of credential storage and execution. */
window.NexoApifySettings={install({root,onDirty}){
 let catalog=null,values={},network='facebook',inputs=[],policy={},policyInputs=null;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 function capture(){for(const {key,selected,max,daily,task,dataset,definition} of inputs)values[key]={selected:selected.checked,actor_ref:definition.actor_ref,max_items:Number(max.value),daily_limit:Number(daily.value),task_ref:task?.value.trim()||'',dataset_ref:dataset?.value.trim()||''};if(policyInputs){policy={mode:policyInputs.mode.value,monthly_budget_usd:policyInputs.month.value,per_run_usd:policyInputs.cap.value,account_limit:Number(policyInputs.accounts.value)};}}
 function field(card,label,value,type='text',limits={}){const l=el('label',label),input=el('input');input.type=type;input.value=String(value);for(const [k,v] of Object.entries(limits))input[k]=v;input.oninput=()=>{capture();onDirty();};l.append(input);card.append(l);return input;}
 function render(){root.replaceChildren();inputs=[];policyInputs=null;if(!catalog)return;
  root.append(el('h4','Redes y procesos de este proyecto'),el('p','Un solo token de Apify. Elige qué preparar en cada red y guarda al terminar.','note'));
  const budget=el('div',undefined,'apify-process'),label=el('label','Ejecución de Facebook'),mode=el('select');
  for(const [key,title] of [['paused','Pausado'],['test','Prueba única · 1 cuenta, hasta 3 publicaciones'],['scheduled','Procesos seleccionados · diario a las 08:00']]){const option=el('option',title);option.value=key;mode.append(option);}mode.value=policy.mode||'paused';label.append(mode);budget.append(label);
  const budgetFields=el('div',undefined,'apify-process-fields'),month=field(budgetFields,'Presupuesto mensual máximo · USD',policy.monthly_budget_usd||'0','number',{min:0,max:100,step:'0.01',required:true}),cap=field(budgetFields,'Límite por ejecución de Actor · USD',policy.per_run_usd||'0','number',{min:0,max:1,step:'0.01',required:true}),accounts=field(budgetFields,'Máximo de cuentas por corte',policy.account_limit||1,'number',{min:1,max:5,required:true});
  policyInputs={mode,month,cap,accounts};mode.onchange=()=>{capture();onDirty();};budget.append(budgetFields,el('p','La prueba usa solo la cuenta principal y publicaciones. Operación diaria usa los procesos de Facebook seleccionados. Al guardar un modo activo autorizas consumo dentro de estos límites. Las reservas se conservan ante fallos; no son una factura.','note'));root.append(budget);
  const nav=el('div',undefined,'apify-network-tabs');nav.setAttribute('role','group');nav.setAttribute('aria-label','Red social de Apify');
  for(const [key,name] of Object.entries(catalog.networks)){const b=el('button',name);b.type='button';b.setAttribute('aria-pressed',String(key===network));b.onclick=()=>{capture();network=key;render();};nav.append(b);}root.append(nav);
  const list=el('div',undefined,'apify-process-list');
  for(const definition of catalog.processes.filter(p=>p.network===network)){
   const v=values[definition.key]||{selected:false,max_items:20,daily_limit:1,task_ref:'',dataset_ref:''};
   const card=el('div',undefined,'apify-process'),head=el('label',undefined,'apify-process-choice'),selected=el('input');selected.type='checkbox';selected.checked=v.selected;selected.onchange=()=>{capture();onDirty();};head.append(selected,el('strong',definition.label));card.append(head);
   const a=el('a',definition.actor_ref);a.href=definition.url;a.target='_blank';a.rel='noopener noreferrer';card.append(a);
   if(definition.mode)card.append(el('small','Modo: '+definition.mode+(definition.transport==='standby'?' · API directa de Apify':'')));
   const grid=el('div',undefined,'apify-process-fields');
   const max=field(grid,'Resultados por consulta',v.max_items,'number',{min:1,max:500,required:true}),daily=field(grid,'Consultas máximas por día',v.daily_limit,'number',{min:0,max:2,required:true});
   let task=null,dataset=null;
   if(definition.transport!=='standby'){
    task=field(grid,'ID de tarea de Apify · opcional',v.task_ref,'text',{maxLength:100,pattern:'[A-Za-z0-9_-]*'});
    dataset=field(grid,'ID de dataset existente · opcional',v.dataset_ref,'text',{maxLength:100,pattern:'[A-Za-z0-9_-]*'});
   }
   card.append(grid);list.append(card);inputs.push({key:definition.key,selected,max,daily,task,dataset,definition});
  }root.append(list);
  root.append(el('p','Las cuentas públicas se registran una sola vez en Actores y Medios. Los límites son por proceso y proyecto; no equivalen a un tope monetario.','note'));
 }
 return{show(row){catalog=row?.kind==='apify'?row.apify_catalog:null;values=JSON.parse(JSON.stringify(row?.settings?.apify_processes||{}));policy=row?.execution||{};if(!catalog?.networks[network])network='facebook';root.hidden=!catalog;render();},collect(){capture();return JSON.parse(JSON.stringify(values));},collectExecution(){capture();return {...policy};},reset(){catalog=null;values={};policy={};policyInputs=null;inputs=[];network='facebook';root.replaceChildren();root.hidden=true;}};
}};
