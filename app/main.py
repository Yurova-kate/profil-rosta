"""Профиль роста: минимальный рабочий API. Только демонстрационные данные."""
import os, sqlite3, secrets, hashlib, hmac, io
from pathlib import Path
from contextlib import contextmanager
from fastapi import FastAPI, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from docx import Document

ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.environ.get("PROFILE_DB", str(ROOT/"profile.db")))
app=FastAPI(title="Профиль роста",version="0.1.0")

@contextmanager
def database():
    DB.parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(DB)
    db.row_factory=sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    try:
        yield db
        db.commit()
    finally:
        db.close()

def hash_password(password,salt=None):
    salt=salt or secrets.token_hex(16)
    return salt+":"+hashlib.pbkdf2_hmac("sha256",password.encode(),bytes.fromhex(salt),250000).hex()

def verify(password,stored):
    return hmac.compare_digest(hash_password(password,stored.split(":")[0]),stored)

def init_db():
    with database() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,role TEXT NOT NULL CHECK(role IN ('admin','manager','employee')),manager_id INTEGER REFERENCES users(id),password_hash TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id INTEGER NOT NULL REFERENCES users(id));
        CREATE TABLE IF NOT EXISTS skills(id INTEGER PRIMARY KEY,employee_id INTEGER NOT NULL REFERENCES users(id),name TEXT NOT NULL,verified_by INTEGER REFERENCES users(id),UNIQUE(employee_id,name));
        CREATE TABLE IF NOT EXISTS projects(id INTEGER PRIMARY KEY,employee_id INTEGER NOT NULL REFERENCES users(id),title TEXT NOT NULL,description TEXT NOT NULL DEFAULT '');
        CREATE TABLE IF NOT EXISTS certifications(id INTEGER PRIMARY KEY,skill_keyword TEXT NOT NULL,exam_title TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS employee_profiles(employee_id INTEGER PRIMARY KEY REFERENCES users(id),job_title TEXT NOT NULL DEFAULT '',specialization TEXT NOT NULL DEFAULT '',grade TEXT NOT NULL DEFAULT '',years_experience INTEGER,about TEXT NOT NULL DEFAULT '',updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS employee_certifications(id INTEGER PRIMARY KEY,employee_id INTEGER NOT NULL REFERENCES users(id),certification_id INTEGER NOT NULL REFERENCES certifications(id),certificate_number TEXT NOT NULL,passport_url TEXT,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,UNIQUE(employee_id,certification_id,certificate_number));
        """)

@app.on_event("startup")
def startup():
    init_db()

class Account(BaseModel):
    email:str
    name:str
    password:str=Field(min_length=10)
class NewUser(Account):
    role:str
    manager_id:int|None=None
class Login(BaseModel):
    email:str
    password:str
class Skill(BaseModel):
    name:str=Field(min_length=2,max_length=120)
class Project(BaseModel):
    title:str=Field(min_length=2,max_length=200)
    description:str=""
class ProfileUpdate(BaseModel):
    job_title:str=Field(default="",max_length=160)
    specialization:str=Field(default="",max_length=160)
    grade:str=Field(default="",max_length=80)
    years_experience:int|None=Field(default=None,ge=0,le=70)
    about:str=Field(default="",max_length=3000)

class EmployeeCertificate(BaseModel):
    certification_id:int
    certificate_number:str=Field(min_length=1,max_length=120)
    passport_url:str|None=None

class Exam(BaseModel):
    skill_keyword:str
    exam_title:str

def current(authorization:str|None=Header(default=None)):
    token=(authorization or "").removeprefix("Bearer ").strip()
    with database() as db:
        row=db.execute("SELECT u.id,u.email,u.name,u.role,u.manager_id FROM users u JOIN sessions s ON s.user_id=u.id WHERE s.token=?",(token,)).fetchone()
    if not row: raise HTTPException(401,"Требуется авторизация")
    return dict(row)

def access(actor,employee_id,write=False):
    if actor["role"]=="admin" or actor["id"]==employee_id: return
    if actor["role"]=="manager":
        with database() as db:
            employee=db.execute("SELECT manager_id FROM users WHERE id=?",(employee_id,)).fetchone()
        if employee and employee["manager_id"]==actor["id"] and not write: return
    raise HTTPException(403,"Недостаточно прав")

@app.post("/api/bootstrap")
def bootstrap(data:Account):
    init_db()
    with database() as db:
        if db.execute("SELECT 1 FROM users LIMIT 1").fetchone(): raise HTTPException(409,"Администратор уже создан")
        db.execute("INSERT INTO users(email,name,role,password_hash) VALUES(?,?,'admin',?)",(data.email.lower(),data.name,hash_password(data.password)))
    return {"ok":True}

@app.post("/api/login")
def login(data:Login):
    with database() as db:
        row=db.execute("SELECT * FROM users WHERE email=?",(data.email.lower(),)).fetchone()
        if not row or not verify(data.password,row["password_hash"]): raise HTTPException(401,"Неверные учётные данные")
        token=secrets.token_urlsafe(32)
        db.execute("INSERT INTO sessions(token,user_id) VALUES(?,?)",(token,row["id"]))
    return {"token":token,"role":row["role"],"user_id":row["id"]}

@app.get("/api/me")
def me(authorization:str|None=Header(default=None)):
    return current(authorization)

@app.post("/api/users")
def add_user(data:NewUser,authorization:str|None=Header(default=None)):
    actor=current(authorization)
    if actor["role"]!="admin": raise HTTPException(403,"Только администратор")
    if data.role not in ("admin","manager","employee"): raise HTTPException(422,"Неизвестная роль")
    with database() as db:
        if data.manager_id and not db.execute("SELECT 1 FROM users WHERE id=? AND role='manager'",(data.manager_id,)).fetchone(): raise HTTPException(422,"Руководитель не найден")
        try:
            cur=db.execute("INSERT INTO users(email,name,role,manager_id,password_hash) VALUES(?,?,?,?,?)",(data.email.lower(),data.name,data.role,data.manager_id,hash_password(data.password)))
        except sqlite3.IntegrityError: raise HTTPException(409,"Email уже существует")
        return {"id":cur.lastrowid}

@app.get("/api/users")
def users(authorization:str|None=Header(default=None)):
    actor=current(authorization)
    with database() as db:
        if actor["role"]=="admin": rows=db.execute("SELECT id,email,name,role,manager_id FROM users").fetchall()
        elif actor["role"]=="manager": rows=db.execute("SELECT id,email,name,role,manager_id FROM users WHERE id=? OR manager_id=?",(actor["id"],actor["id"])).fetchall()
        else: rows=db.execute("SELECT id,email,name,role,manager_id FROM users WHERE id=?",(actor["id"],)).fetchall()
    return [dict(r) for r in rows]

@app.get("/api/users/{employee_id}/profile")
def profile(employee_id:int,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id)
    with database() as db:
        person=db.execute("SELECT id,email,name,role,manager_id FROM users WHERE id=?",(employee_id,)).fetchone()
        if not person: raise HTTPException(404,"Сотрудник не найден")
        details=db.execute("SELECT job_title,specialization,grade,years_experience,about,updated_at FROM employee_profiles WHERE employee_id=?",(employee_id,)).fetchone()
        skills=[dict(r) for r in db.execute("SELECT id,name,verified_by FROM skills WHERE employee_id=?",(employee_id,))]
        projects=[dict(r) for r in db.execute("SELECT id,title,description FROM projects WHERE employee_id=?",(employee_id,))]
        competency_rows=[dict(r) for r in db.execute("""SELECT c.name,ec.level
          FROM employee_competencies ec JOIN competency_catalog c ON c.id=ec.competency_id
          WHERE ec.employee_id=? ORDER BY c.category,c.name""",(employee_id,))] if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='employee_competencies'").fetchone() else []
        recommendations=[dict(r) for r in db.execute("SELECT DISTINCT c.id,c.exam_title FROM certifications c JOIN skills s ON lower(s.name) LIKE '%'||lower(c.skill_keyword)||'%' WHERE s.employee_id=?",(employee_id,))]
        certificates=[dict(r) for r in db.execute("SELECT ec.id,ec.certification_id,c.exam_title,ec.certificate_number,ec.passport_url FROM employee_certifications ec JOIN certifications c ON c.id=ec.certification_id WHERE ec.employee_id=? ORDER BY ec.id DESC",(employee_id,))]
    return {"employee":dict(person),"details":dict(details) if details else {"job_title":"","specialization":"","grade":"","years_experience":None,"about":""},"skills":skills,"competency_rows":competency_rows,"projects":projects,"certifications":recommendations,"earned_certifications":certificates}

@app.post("/api/users/{employee_id}/skills")
def add_skill(employee_id:int,data:Skill,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id,write=True)
    with database() as db:
        try: cur=db.execute("INSERT INTO skills(employee_id,name) VALUES(?,?)",(employee_id,data.name.strip()))
        except sqlite3.IntegrityError: raise HTTPException(409,"Навык уже указан")
        return {"id":cur.lastrowid}

@app.post("/api/users/{employee_id}/projects")
def add_project(employee_id:int,data:Project,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id,write=True)
    with database() as db:
        cur=db.execute("INSERT INTO projects(employee_id,title,description) VALUES(?,?,?)",(employee_id,data.title,data.description))
        return {"id":cur.lastrowid}

@app.post("/api/certifications")
def add_certification(data:Exam,authorization:str|None=Header(default=None)):
    actor=current(authorization)
    if actor["role"]!="admin": raise HTTPException(403,"Только администратор")
    with database() as db:
        cur=db.execute("INSERT INTO certifications(skill_keyword,exam_title) VALUES(?,?)",(data.skill_keyword,data.exam_title))
        return {"id":cur.lastrowid}

@app.get("/api/users/{employee_id}/resume.docx")
def resume(employee_id:int,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id)
    data=profile(employee_id,authorization)
    doc=Document()
    doc.add_heading("Проектное резюме",0)
    doc.add_heading(data["employee"]["name"],level=1)
    details=data["details"]
    for label,key in (("Должность","job_title"),("Специализация","specialization"),("Грейд","grade"),("Опыт, лет","years_experience")):
        if details.get(key) is not None and details.get(key)!="":
            doc.add_paragraph(label+": "+str(details[key]))
    if details.get("about"): doc.add_paragraph(details["about"])
    doc.add_heading("Компетенции",level=2)
    for s in data["skills"]: doc.add_paragraph(s["name"],style="List Bullet")
    doc.add_heading("Сертификации",level=2)
    for cert in data["earned_certifications"]:
        doc.add_paragraph(cert["exam_title"]+" — № "+cert["certificate_number"]+((" — "+cert["passport_url"]) if cert["passport_url"] else ""),style="List Bullet")
    doc.add_heading("Компетенции из справочника",level=2)
    levels={"beginner":"Начальный","intermediate":"Рабочий","advanced":"Продвинутый","expert":"Экспертный"}
    for competency in data["competency_rows"]:
        doc.add_paragraph(competency["name"]+" — "+levels.get(competency["level"],competency["level"])+"",style="List Bullet")
    doc.add_heading("Проектный опыт",level=2)
    for p in data["projects"]:
        doc.add_heading(p["title"],level=3)
        doc.add_paragraph(p["description"])
    buffer=io.BytesIO();doc.save(buffer);buffer.seek(0)
    return StreamingResponse(buffer,media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",headers={"Content-Disposition":'attachment; filename="resume.docx"'})

# Serve the same-origin UI; the API remains under /api.
from fastapi.responses import FileResponse

@app.get("/", include_in_schema=False)
def index():
    return FileResponse(ROOT / "web" / "index.html")

@app.get("/api/certifications/catalog")
def certification_catalog(authorization:str|None=Header(default=None)):
    current(authorization)
    with database() as db:
        return [dict(r) for r in db.execute("SELECT id,exam_title,skill_keyword FROM certifications ORDER BY exam_title,id")]

@app.post("/api/users/{employee_id}/certifications")
def add_employee_certificate(employee_id:int,data:EmployeeCertificate,authorization:str|None=Header(default=None)):
    from urllib.parse import urlsplit
    actor=current(authorization);access(actor,employee_id,write=True)
    number=data.certificate_number.strip()
    if not number: raise HTTPException(422,"Укажите номер сертификата")
    url=(data.passport_url or "").strip() or None
    if url:
        parts=urlsplit(url)
        if parts.scheme!="https" or not parts.hostname or parts.username or parts.password or len(url)>2000:
            raise HTTPException(422,"Укажите корректную HTTPS-ссылку на паспорт сертификата")
    with database() as db:
        if not db.execute("SELECT 1 FROM certifications WHERE id=?",(data.certification_id,)).fetchone():
            raise HTTPException(404,"Сертификация отсутствует в каталоге")
        try:
            cur=db.execute("INSERT INTO employee_certifications(employee_id,certification_id,certificate_number,passport_url) VALUES(?,?,?,?)",(employee_id,data.certification_id,number,url))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"Этот сертификат уже добавлен")
    return {"id":cur.lastrowid}

@app.delete("/api/users/{employee_id}/certifications/{record_id}")
def delete_employee_certificate(employee_id:int,record_id:int,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id,write=True)
    with database() as db:
        result=db.execute("DELETE FROM employee_certifications WHERE id=? AND employee_id=?",(record_id,employee_id))
        if not result.rowcount: raise HTTPException(404,"Запись не найдена")
    return {"ok":True}

@app.put("/api/users/{employee_id}/profile")
def update_profile(employee_id:int,data:ProfileUpdate,authorization:str|None=Header(default=None)):
    actor=current(authorization);access(actor,employee_id,write=True)
    with database() as db:
        if not db.execute("SELECT 1 FROM users WHERE id=?",(employee_id,)).fetchone():
            raise HTTPException(404,"Сотрудник не найден")
        db.execute("""INSERT INTO employee_profiles(employee_id,job_title,specialization,grade,years_experience,about)
        VALUES(?,?,?,?,?,?)
        ON CONFLICT(employee_id) DO UPDATE SET job_title=excluded.job_title,
        specialization=excluded.specialization,grade=excluded.grade,
        years_experience=excluded.years_experience,about=excluded.about,
        updated_at=CURRENT_TIMESTAMP""",
        (employee_id,data.job_title.strip(),data.specialization.strip(),data.grade.strip(),data.years_experience,data.about.strip()))
    return {"ok":True}
