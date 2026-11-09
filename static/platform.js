/* Local control plane. Credentials are only submitted on explicit form action. */
window.NexoPlatform={install({api,byId,onProjectsChanged,onBrandChanged}){
 let permitted=false,cloudAuth=false;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 const message=text=>{byId('platformMessage').textContent=text;};
 const send=(path,body,method='POST')=>api('/api/platform/'+path,{method,headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 async function reload(){
  const state=await api('/api/platform/session');permitted=state.is_superadmin;cloudAuth=state.auth_mode==='supabase';
  byId('platformUserTitle').textContent=cloudAuth?'Vincular cuenta de Supabase':'Cuenta local';
  byId('platformUserSave').textContent=cloudAuth?'Vincular cuenta':'Crear cuenta local';
  byId('platformUserHelp').textContent=cloudAuth?'Crea la cuenta y su contraseña en Supabase. Después registra aquí su correo e ID y asígnale un proyecto. No recibe permisos de superadministrador.':'No reutilices contraseñas de nube. Esta cuenta no recibe permisos de plataforma.';
  byId('platformUserPassword').hidden=cloudAuth;byId('platformPasswordLabel').hidden=cloudAuth;byId('platformUserPassword').required=!cloudAuth;
  byId('platformUserSubject').hidden=!cloudAuth;byId('platformSubjectLabel').hidden=!cloudAuth;byId('platformUserSubject').required=cloudAuth;
  if(cloudAuth)byId('platformUserPassword').value='';
  document.documentElement?.setAttribute('data-nexo-access',permitted?'owner':'reader');
  document.documentElement?.setAttribute('data-visual-review',state.visual_review?'true':'false');
  byId('platformNav').hidden=!permitted;byId('platformForms').hidden=!permitted;
  if(!permitted)return;
  const [projects,users]=await Promise.all([api('/api/platform/projects'),api('/api/platform/users')]);
  const list=byId('platformProjects');list.replaceChildren();
  for(const p of projects){const row=el('article',undefined,'dataset-item');row.append(el('b',p.name),el('p',p.slug+' · '+p.status,'note'));
   const button=el('button','Consultar membresías','outline');button.type='button';button.onclick=async()=>{try{
    const members=await api('/api/platform/projects/'+p.id+'/members');const detail=el('p',members.map(m=>(users.find(u=>u.id===m.user_id)?.email||'Cuenta #'+m.user_id)+' · '+m.role).join('\n'),'note');detail.style.whiteSpace='pre-wrap';row.append(detail);
   }catch(e){message(e.message);}};row.append(button);list.append(row);
  }
  for(const id of ['platformOwner','platformMemberUser']){const select=byId(id);select.replaceChildren();
   if(id==='platformOwner'){const option=el('option','Mi cuenta actual');option.value='';select.append(option);}
   for(const user of users.filter(x=>x.active)){const option=el('option',user.email);option.value=user.id;select.append(option);}}
  const pselect=byId('platformMemberProject');pselect.replaceChildren();for(const p of projects){const option=el('option',p.name);option.value=p.id;pselect.append(option);}
  const accounts=byId('platformUsers');accounts.replaceChildren();
  for(const user of users){const row=el('div',undefined,'pulse-setting-row');row.append(el('span',user.email+' · '+(user.active?'activa':'desactivada')));
   const button=el('button',user.active?'Desactivar':'Reactivar','outline');button.type='button';button.onclick=async()=>{try{await send('users/'+user.id,{active:!user.active},'PATCH');await reload();message('Estado de cuenta actualizado.');}catch(e){message(e.message);}};row.append(button);accounts.append(row);}
 }
 byId('platformProjectForm').onsubmit=async event=>{event.preventDefault();try{
  const body={name:byId('platformProjectName').value,slug:byId('platformProjectSlug').value,territory:byId('platformTerritory').value};
  if(byId('platformOwner').value)body.owner_user_id=Number(byId('platformOwner').value);
  const result=await send('projects',body);byId('platformProjectForm').reset();await reload();await onProjectsChanged();message('Proyecto creado: '+result.name+'. Sus datos están separados.');
 }catch(e){message(e.message);}};
 byId('platformMemberForm').onsubmit=async event=>{event.preventDefault();try{
  await send('projects/'+Number(byId('platformMemberProject').value)+'/members',{user_id:Number(byId('platformMemberUser').value),role:byId('platformMemberRole').value},'PUT');
  await reload();await onProjectsChanged();message('Membresía actualizada. Esto no concede administración de plataforma.');
 }catch(e){message(e.message);}};
 byId('platformUserForm').onsubmit=async event=>{event.preventDefault();const button=byId('platformUserSave');button.disabled=true;
  try{const body={email:byId('platformUserEmail').value};if(cloudAuth)body.auth_subject=byId('platformUserSubject').value.trim();else body.password=byId('platformUserPassword').value;await send('users',body);byId('platformUserPassword').value='';byId('platformUserForm').reset();await reload();message(cloudAuth?'Cuenta vinculada. Asigna una membresía de proyecto.':'Cuenta local creada sin permisos de plataforma. Asigna una membresía de proyecto.');}
  catch(e){message(e.message);}finally{button.disabled=false;}
 };
 return {reload,allowed:()=>permitted};
}};
