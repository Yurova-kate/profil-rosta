/* Development-plan UI: loaded after the core application. */
function developmentView(){
  const editable=me.role==='admin'||me.id===selected;
  const statuses={planned:'Запланировано',in_progress:'В работе',completed:'Выполнено',cancelled:'Отменено'};
  const levels={beginner:'Начальный',intermediate:'Рабочий',advanced:'Продвинутый',expert:'Экспертный'};
  const competencyOptions=(id)=>'<option value="">Без привязки</option>'+competencyCatalog.map(c=>'<option value="'+c.id+'" '+(c.id===id?'selected':'')+'>'+esc(c.name)+'</option>').join('');
  const levelOptions=(value)=>'<option value="">Не задан</option>'+Object.entries(levels).map(([k,v])=>'<option value="'+k+'" '+(k===value?'selected':'')+'>'+v+'</option>').join('');
  const certOptions=(id)=>'<option value="">Без сертификации</option>'+catalog.map(x=>'<option value="'+x.id+'" '+(x.id===id?'selected':'')+'>'+esc(x.exam_title)+'</option>').join('');
  const fields=(g)=>'<label>Название цели</label><input name="title" minlength="3" maxlength="180" required value="'+esc(g.title||'')+'"><label>Компетенция</label><select name="competency_id">'+competencyOptions(g.competency_id)+'</select><label>Целевой уровень</label><select name="target_level">'+levelOptions(g.target_level)+'</select><label>Сертификация 1С</label><select name="certification_id">'+certOptions(g.certification_id)+'</select><label>Срок</label><input name="due_date" type="date" value="'+esc(g.due_date||'')+'"><label>Действия</label><textarea name="actions" maxlength="3000">'+esc(g.actions||'')+'</textarea>';
  const total=developmentGoals.filter(g=>g.status!=='cancelled').length;
  const completed=developmentGoals.filter(g=>g.status==='completed').length;
  const progress=total?Math.round(completed/total*100):0;
  const summary='<div class="notice"><strong>Выполнено '+completed+' из '+total+' целей ('+progress+'%)</strong><div role="progressbar" aria-label="Прогресс плана развития" aria-valuemin="0" aria-valuemax="100" aria-valuenow="'+progress+'" style="height:10px;background:#dce5fa;border-radius:9px;overflow:hidden;margin-top:10px"><div style="width:'+progress+'%;height:100%;background:#315ce8"></div></div></div>';
  const existing=developmentGoals.map(g=>'<div class="item"><strong>'+esc(g.title)+'</strong><p class="muted">'+esc(statuses[g.status]||g.status)+' · '+esc(g.due_date||'Без срока')+(g.competency_name?' · '+esc(g.competency_name):'')+(g.certification_name?' · '+esc(g.certification_name):'')+'</p>'+(editable?'<details><summary>Редактировать</summary><form data-goal-edit="'+g.id+'">'+fields(g)+'<label>Статус</label><select name="status">'+Object.entries(statuses).map(([k,v])=>'<option value="'+k+'" '+(k===g.status?'selected':'')+'>'+v+'</option>').join('')+'</select><button>Сохранить</button> <button type="button" class="ghost" data-goal-delete="'+g.id+'">Удалить</button></form></details>':'<p>'+esc(g.actions||'')+'</p>')+'</div>').join('');
  return '<div class="card"><h2>Индивидуальный план развития</h2><p class="muted">Цели не изменяют текущий уровень компетенций.</p>'+summary+(existing||'<p class="muted">Целей пока нет.</p>')+'</div>'+(editable?'<div class="card"><h3>Новая цель</h3><form id="newGoal">'+fields({})+'<button>Добавить цель</button></form></div>':'');
}
function bindDevelopment(){
  const payload=form=>{const d=Object.fromEntries(new FormData(form));return {...d,competency_id:d.competency_id?Number(d.competency_id):null,target_level:d.target_level||null,certification_id:d.certification_id?Number(d.certification_id):null,due_date:d.due_date||null}};
  const submit=async(form,path,method)=>{try{await json(path,{method,body:payload(form)});await loadDevelopment();alertMessage('План развития сохранён')}catch(e){alertMessage(e.message,true)}};
  const form=document.getElementById('newGoal');
  if(form)form.onsubmit=e=>{e.preventDefault();submit(form,'/users/'+selected+'/development','POST')};
  document.querySelectorAll('[data-goal-edit]').forEach(f=>f.onsubmit=e=>{e.preventDefault();submit(f,'/users/'+selected+'/development/'+f.dataset.goalEdit,'PUT')});
  document.querySelectorAll('[data-goal-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('Удалить цель?'))return;try{await api('/users/'+selected+'/development/'+b.dataset.goalDelete,{method:'DELETE'});await loadDevelopment();alertMessage('Цель удалена')}catch(e){alertMessage(e.message,true)}});
}
