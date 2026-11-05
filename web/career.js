/* Career screens use the existing authenticated api/json/esc helpers. */
let careerData={work_experiences:[],projects:[]};
async function loadCareer(){careerData=await json('/users/'+selected+'/career')}
const careerDate=d=>d?new Date(d+'T12:00:00').toLocaleDateString('ru-RU',{month:'short',year:'numeric'}):'по настоящее время';
const careerLabel=(a,b)=>[a?careerDate(a):'Дата не указана',careerDate(b)].join(' — ');
function formField(name,label,value='',type='text',required=false){
 return '<label>'+esc(label)+'</label>'+(type==='textarea'?'<textarea name="'+name+'">'+esc(value||'')+'</textarea>':'<input type="'+type+'" name="'+name+'" value="'+esc(value||'')+'" '+(required?'required':'')+'>');
}
function workForm(w={}){
 return '<form data-career-form="work" data-id="'+(w.id||'')+'" class="career-form">'+
 formField('company','Компания',w.company,'text',true)+
 formField('position','Должность',w.position,'text',true)+
 '<div class="career-form-grid">'+formField('start_date','Начало работы',w.start_date,'date',true)+formField('end_date','Окончание (если не работаете)',w.end_date,'date')+'</div>'+
 '<label class="career-check"><input type="checkbox" name="current" '+(w.current?'checked':'')+'> Работаю сейчас</label>'+
 formField('description','Зоны ответственности',w.description,'textarea')+
 formField('achievements','Достижения и результаты',w.achievements,'textarea')+
 '<button type="submit">'+(w.id?'Сохранить изменения':'Добавить место работы')+'</button></form>';
}
function projectForm(p={}){
 const entries=careerData.work_experiences||[];
 return '<form data-career-form="project" data-id="'+(p.id||'')+'" class="career-form">'+
 formField('title','Название проекта',p.title,'text',true)+formField('role','Роль в проекте',p.role)+
 '<label>Связать с местом работы</label><select name="work_experience_id"><option value="">Не привязан</option>'+
 entries.map(w=>'<option value="'+w.id+'" '+(Number(p.work_experience_id)===w.id?'selected':'')+'>'+esc(w.company)+' · '+esc(w.position)+'</option>').join('')+'</select>'+
 formField('organization','Заказчик / организация',p.organization)+
 '<div class="career-form-grid">'+formField('start_date','Начало проекта',p.start_date,'date')+formField('end_date','Завершение',p.end_date,'date')+'</div>'+
 formField('description','Задачи и вклад',p.description,'textarea')+
 formField('technologies','Технологии и инструменты',p.technologies)+
 formField('outcomes','Результаты проекта',p.outcomes,'textarea')+
 '<button type="submit">'+(p.id?'Сохранить изменения':'Добавить проект')+'</button></form>';
}
function careerView(mode){
 const editable=me.role==='admin'||me.id===selected;
 const work=careerData.work_experiences||[],projects=careerData.projects||[];
 const isWork=mode==='experience',records=isWork?work:projects;
 const count=records.length, noun=isWork?'мест работы':'проектов';
 const pageTitle=isWork?'Опыт работы':'Проектный опыт';
 const intro=isWork?'Все компании и должности в единой хронологии.':'Проекты, роли, стек и измеримые результаты — отдельно для каждого участия.';
 const create=isWork?workForm():projectForm();
 const items=records.map(item=>{
   const title=isWork?item.position:item.title;
   const sub=isWork?item.company:(item.role||'Роль не указана')+(item.organization?' · '+item.organization:'');
   const details=isWork?item.description:item.description;
   const result=isWork?item.achievements:item.outcomes;
   const editing=isWork?workForm(item):projectForm(item);
   return '<article class="career-entry"><div class="career-entry-top"><span class="career-dot"></span><div class="career-entry-body"><div class="row"><div><h3>'+esc(title)+'</h3><p class="muted small">'+esc(sub)+'</p></div><span class="career-period">'+esc(careerLabel(item.start_date,item.end_date))+'</span></div>'+
    (details?'<p>'+esc(details)+'</p>':'')+(result?'<p class="career-outcome"><strong>Результат:</strong> '+esc(result)+'</p>':'')+
    (!isWork&&item.technologies?'<p class="small muted"><strong>Стек:</strong> '+esc(item.technologies)+'</p>':'')+
    (editable?'<details class="career-edit"><summary>Редактировать запись</summary>'+editing+'<button type="button" class="career-danger" data-career-delete="'+(isWork?'work':'project')+'" data-id="'+item.id+'">Удалить запись</button></details>':'')+
   '</div></div></article>';
 }).join('');
 return '<section class="card career-page"><div class="career-heading"><div><p class="eyebrow">МОЯ КАРЬЕРА</p><h2>'+pageTitle+'</h2><p class="muted">'+intro+'</p></div><span class="career-count">'+count+' '+noun+'</span></div>'+
 (count?'<div class="career-timeline">'+items+'</div>':'<div class="career-empty"><strong>Пока нет записей</strong><p class="muted">Добавьте первую запись, чтобы сформировать профессиональную историю.</p></div>')+
 (editable?'<details class="career-add"><summary>+ '+(isWork?'Добавить место работы':'Добавить проект')+'</summary>'+create+'</details>':'')+
 '</section>';
}
function bindCareer(){
 document.querySelectorAll('[data-career-form]').forEach(form=>form.onsubmit=async event=>{
  event.preventDefault();
  const kind=form.dataset.careerForm,id=form.dataset.id,work=kind==='work';
  const values=Object.fromEntries(new FormData(form));
  if(work)values.current=form.elements.current.checked;
  if(work&&values.current)values.end_date=null;
  for(const key of ['start_date','end_date','work_experience_id'])if(key in values&&!values[key])values[key]=null;
  if(values.work_experience_id)values.work_experience_id=Number(values.work_experience_id);
  const base='/users/'+selected+'/'+(work?'work-experiences':'career/projects');
  const button=form.querySelector('button[type="submit"]');if(button)button.disabled=true;
  try{await json(base+(id?'/'+id:''),{method:id?'PUT':'POST',body:values});await loadCareer();alertMessage('Запись сохранена')}
  catch(err){if(button)button.disabled=false;alertMessage(err.message,true)}
 });
 document.querySelectorAll('[data-career-delete]').forEach(button=>button.onclick=async()=>{
  if(!confirm('Удалить запись? Действие нельзя отменить.'))return;
  const base='/users/'+selected+'/'+(button.dataset.careerDelete==='work'?'work-experiences':'career/projects');
  button.disabled=true;
  try{await api(base+'/'+button.dataset.id,{method:'DELETE'});await loadCareer();alertMessage('Запись удалена')}
  catch(err){button.disabled=false;alertMessage(err.message,true)}
 });
}
