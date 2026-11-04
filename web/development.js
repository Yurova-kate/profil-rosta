/* Development-plan UI: loaded after the core application. */
function developmentView(){
  const editable=me.role==='admin'||me.id===selected;
  const statuses={planned:'Запланировано',in_progress:'В работе',completed:'Выполнено',cancelled:'Отменено'};
  const levels={beginner:'Начальный',intermediate:'Рабочий',advanced:'Продвинутый',expert:'Экспертный'};
  const competencyOptions=(id)=>'<option value="">Без привязки</option>'+competencyCatalog.map(c=>'<option value="'+c.id+'" '+(c.id===id?'selected':'')+'>'+esc(c.name)+'</option>').join('');
  const levelOptions=(value)=>'<option value="">Не задан</option>'+Object.entries(levels).map(([k,v])=>'<option value="'+k+'" '+(k===value?'selected':'')+'>'+v+'</option>').join('');
  const fields=(g)=>'<label>Название цели</label><input name="title" minlength="3" maxlength="180" required value="'+esc(g.title||'')+'"><label>Компетенция</label><select name="competency_id">'+competencyOptions(g.competency_id)+'</select><label>Целевой уровень</label><select name="target_level">'+levelOptions(g.target_level)+'</select><label>Срок</label><input name="due_date" type="date" value="'+esc(g.due_date||'')+'"><label>Действия</label><textarea name="actions" maxlength="3000">'+esc(g.actions||'')+'</textarea>';
  const existing=developmentGoals.map(g=>'<div class="item"><strong>'+esc(g.title)+'</strong><p class="muted">'+esc(statuses[g.status]||g.status)+' · '+esc(g.due_date||'Без срока')+'</p>'+(editable?'<details><summary>Редактировать</summary><form data-goal-edit="'+g.id+'">'+fields(g)+'<label>Статус</label><select name="status">'+Object.entries(statuses).map(([k,v])=>'<option value="'+k+'" '+(k===g.status?'selected':'')+'>'+v+'</option>').join('')+'</select><button>Сохранить</button> <button type="button" class="ghost" data-goal-delete="'+g.id+'">Удалить</button></form></details>':'<p>'+esc(g.actions||'')+'</p>')+'</div>').join('');
  return '<div class="card"><h2>Индивидуальный план развития</h2><p class="muted">Цели не изменяют текущий уровень компетенций.</p>'+(existing||'<p class="muted">Целей пока нет.</p>')+'</div>'+(editable?'<div class="card"><h3>Новая цель</h3><form id="newGoal">'+fields({})+'<button>Добавить цель</button></form></div>':'');
}
function bindDevelopment(){
  const payload=form=>{const d=Object.fromEntries(new FormData(form));return {...d,competency_id:d.competency_id?Number(d.competency_id):null,target_level:d.target_level||null,due_date:d.due_date||null}};
  const submit=async(form,path,method)=>{try{await json(path,{method,body:payload(form)});await loadDevelopment();alertMessage('План развития сохранён')}catch(e){alertMessage(e.message,true)}};
  const form=document.getElementById('newGoal');
  if(form)form.onsubmit=e=>{e.preventDefault();submit(form,'/users/'+selected+'/development','POST')};
  document.querySelectorAll('[data-goal-edit]').forEach(f=>f.onsubmit=e=>{e.preventDefault();submit(f,'/users/'+selected+'/development/'+f.dataset.goalEdit,'PUT')});
  document.querySelectorAll('[data-goal-delete]').forEach(b=>b.onclick=async()=>{if(!confirm('Удалить цель?'))return;try{await api('/users/'+selected+'/development/'+b.dataset.goalDelete,{method:'DELETE'});await loadDevelopment();alertMessage('Цель удалена')}catch(e){alertMessage(e.message,true)}});
}
