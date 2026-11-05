/* Overview: compact, action-oriented landing screen. */
function overviewView(){
 const d=profile.details||{};
 const jobs=careerData.work_experiences||[],projects=careerData.projects||[];
 const goals=developmentGoals||[],completed=goals.filter(g=>g.status==='completed').length;
 const total=goals.length,progress=total?Math.round(completed/total*100):0;
 const recent=projects.slice(0,3),activeGoals=goals.filter(g=>g.status==='in_progress'||g.status==='planned').slice(0,3);
 const canEdit=me.role==='admin'||me.id===selected;
 const tile=(num,label,nav)=>'<button class="overview-stat" type="button" data-go="'+nav+'"><strong>'+num+'</strong><span>'+label+'</span><span class="overview-arrow">↗</span></button>';
 return '<div class="overview">'+
  '<section class="card overview-hero"><div class="overview-hero-copy"><p class="eyebrow">ПРОФЕССИОНАЛЬНЫЙ ПРОФИЛЬ</p><div class="overview-person"><div class="overview-avatar">'+esc((profile.employee.name||'?').slice(0,1).toUpperCase())+'</div><div><h1>'+esc(profile.employee.name)+'</h1><p class="muted">'+esc(d.job_title||'Укажите текущую должность')+(d.specialization?' · '+esc(d.specialization):'')+'</p></div></div><p class="overview-about">'+esc(d.about||'Добавьте несколько предложений о своём опыте, чтобы профиль стал полезнее.')+'</p><div class="overview-actions"><button type="button" data-go="profile">Редактировать профиль</button><button type="button" id="resume" class="ghost">Скачать DOCX</button></div></div></section>'+
  '<section class="overview-metrics">'+tile(jobs.length,'Мест работы','experience')+tile(projects.length,'Проектов','projects')+tile(competencies.length,'Компетенций','competencies')+tile(profile.earned_certifications.length,'Сертификатов','certifications')+'</section>'+
  '<div class="overview-columns"><section class="card"><div class="row"><h2>Карьерный путь</h2><button type="button" class="overview-link" data-go="experience">Вся история ↗</button></div>'+
  (jobs.length?jobs.slice(0,3).map(w=>'<div class="overview-line"><strong>'+esc(w.position)+'</strong><span>'+esc(w.company)+' · '+esc(careerDate(w.start_date))+'</span></div>').join(''):'<div class="overview-empty">Пока нет мест работы. '+(canEdit?'Добавьте первую запись в разделе «Опыт работы».':'')+'</div>')+
  '<div class="row overview-row-bottom"><h3>Последние проекты</h3><button type="button" class="overview-link" data-go="projects">Все проекты ↗</button></div>'+
  (recent.length?recent.map(p=>'<div class="overview-line"><strong>'+esc(p.title)+'</strong><span>'+esc(p.role||p.organization||'Проектный опыт')+'</span></div>').join(''):'<p class="muted small">Проекты пока не добавлены.</p>')+'</section>'+
  '<section class="card"><div class="row"><h2>План развития</h2><button type="button" class="overview-link" data-go="development">Открыть ↗</button></div><div class="overview-progress"><div class="row"><strong>'+progress+'%</strong><span class="muted small">'+completed+' из '+total+' завершено</span></div><div class="overview-track"><div style="width:'+progress+'%"></div></div></div>'+
  (activeGoals.length?activeGoals.map(g=>'<div class="overview-goal"><span class="overview-goal-dot"></span><div><strong>'+esc(g.title)+'</strong><p class="small muted">'+(g.due_date?'До '+esc(new Date(g.due_date+'T12:00:00').toLocaleDateString('ru-RU')):'Срок не указан')+'</p></div></div>').join(''):'<div class="overview-empty">Активных целей пока нет.</div>')+
  '<div class="row overview-row-bottom"><h3>Ключевые компетенции</h3><button type="button" class="overview-link" data-go="competencies">Все ↗</button></div>'+
  (competencies.length?'<div class="overview-chips">'+competencies.slice(0,6).map(c=>'<span class="overview-chip">'+esc(c.name)+'</span>').join('')+'</div>':'<p class="muted small">Добавьте компетенции из каталога 1С.</p>')+'</section></div></div>';
}
function bindOverview(){
 document.querySelectorAll('[data-go]').forEach(button=>button.onclick=()=>{section=button.dataset.go;flash='';render()});
}
