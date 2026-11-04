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
        skills=[dict(r) for r in db.execute("SELECT id,name,verified_by FROM skills WHERE employee_id=?",(employee_id,))]
        projects=[dict(r) for r in db.execute("SELECT id,title,description FROM projects WHERE employee_id=?",(employee_id,))]
        recommendations=[dict(r) for r in db.execute("SELECT DISTINCT c.id,c.exam_title FROM certifications c JOIN skills s ON lower(s.name) LIKE '%'||lower(c.skill_keyword)||'%' WHERE s.employee_id=?",(employee_id,))]
    return {"employee":dict(person),"skills":skills,"projects":projects,"certifications":recommendations}

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

@app.post("/api/users/{employee_id}/skills/{skill_id}/confirm")
def confirm(employee_id:int,skill_id:int,authorization:str|None=Header(default=None)):
    actor=current(authorization)
    if actor["role"]=="employee": raise HTTPException(403,"Только руководитель или администратор")
    if actor["role"]=="manager":
        with database() as db:
            person=db.execute("SELECT manager_id FROM users WHERE id=?",(employee_id,)).fetchone()
        if not person or person["manager_id"]!=actor["id"]: raise HTTPException(403,"Не ваш сотрудник")
    with database() as db:
        cur=db.execute("UPDATE skills SET verified_by=? WHERE id=? AND employee_id=?",(actor["id"],skill_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Навык не найден")
    return {"ok":True}

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
    doc.add_heading("Компетенции",level=2)
    for s in data["skills"]: doc.add_paragraph(s["name"]+(" — подтверждено" if s["verified_by"] else " — заявлено"),style="List Bullet")
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
