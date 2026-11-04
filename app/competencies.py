"""Canonical competency catalog and employee assignments."""
import sqlite3
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from . import main

router=APIRouter(prefix="/api")

class CatalogEntry(BaseModel):
    name:str=Field(min_length=2,max_length=120)
    category:str=Field(min_length=2,max_length=120)
    description:str=Field(default="",max_length=1000)

class Assignment(BaseModel):
    competency_id:int
    level:str

class LevelChange(BaseModel):
    level:str

LEVELS={"beginner","intermediate","advanced","expert"}

def initialize():
    with main.database() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS competency_catalog(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL COLLATE NOCASE UNIQUE,
          category TEXT NOT NULL,
          description TEXT NOT NULL DEFAULT '',
          active INTEGER NOT NULL DEFAULT 1);
        CREATE TABLE IF NOT EXISTS competency_aliases(
          id INTEGER PRIMARY KEY,
          competency_id INTEGER NOT NULL REFERENCES competency_catalog(id),
          alias TEXT NOT NULL COLLATE NOCASE UNIQUE);
        CREATE TABLE IF NOT EXISTS employee_competencies(
          id INTEGER PRIMARY KEY,
          employee_id INTEGER NOT NULL REFERENCES users(id),
          competency_id INTEGER NOT NULL REFERENCES competency_catalog(id),
          level TEXT NOT NULL CHECK(level IN ('beginner','intermediate','advanced','expert')),
          verified_by INTEGER REFERENCES users(id),
          UNIQUE(employee_id,competency_id));
        """)

def actor(auth):
    return main.current(auth)

def require_admin(user):
    if user["role"]!="admin":
        raise HTTPException(403,"Только администратор")

@router.get("/competencies/catalog")
def catalog(authorization:str|None=Header(default=None)):
    actor(authorization)
    with main.database() as db:
        return [dict(row) for row in db.execute(
          "SELECT id,name,category,description FROM competency_catalog WHERE active=1 ORDER BY category,name")]

@router.post("/competencies/catalog")
def create(data:CatalogEntry,authorization:str|None=Header(default=None)):
    require_admin(actor(authorization))
    name=data.name.strip()
    if len(name)<2 or len(data.category.strip())<2:
        raise HTTPException(422,"Укажите название и категорию")
    with main.database() as db:
        try:
            cur=db.execute("INSERT INTO competency_catalog(name,category,description) VALUES(?,?,?)",
              (name,data.category.strip(),data.description.strip()))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"Компетенция уже существует")
        return {"id":cur.lastrowid}

@router.post("/users/{employee_id}/competencies")
def assign(employee_id:int,data:Assignment,authorization:str|None=Header(default=None)):
    user=actor(authorization)
    main.access(user,employee_id,write=True)
    if data.level not in LEVELS:
        raise HTTPException(422,"Некорректный уровень")
    with main.database() as db:
        if not db.execute("SELECT 1 FROM competency_catalog WHERE id=? AND active=1",
                          (data.competency_id,)).fetchone():
            raise HTTPException(404,"Компетенция не найдена")
        try:
            cur=db.execute("INSERT INTO employee_competencies(employee_id,competency_id,level) VALUES(?,?,?)",
                           (employee_id,data.competency_id,data.level))
        except sqlite3.IntegrityError:
            raise HTTPException(409,"Компетенция уже назначена")
        return {"id":cur.lastrowid}

@router.get("/users/{employee_id}/competencies")
def employee_competencies(employee_id:int,authorization:str|None=Header(default=None)):
    main.access(actor(authorization),employee_id)
    with main.database() as db:
        return [dict(row) for row in db.execute("""
          SELECT ec.id,ec.competency_id,c.name,c.category,ec.level
          FROM employee_competencies ec JOIN competency_catalog c ON c.id=ec.competency_id
          WHERE ec.employee_id=? ORDER BY c.category,c.name""",(employee_id,))]

@router.put("/users/{employee_id}/competencies/{assignment_id}")
def change_level(employee_id:int,assignment_id:int,data:LevelChange,authorization:str|None=Header(default=None)):
    main.access(actor(authorization),employee_id,write=True)
    if data.level not in LEVELS:
        raise HTTPException(422,"Некорректный уровень")
    with main.database() as db:
        cur=db.execute("UPDATE employee_competencies SET level=? WHERE id=? AND employee_id=?",
                       (data.level,assignment_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Компетенция не найдена")
    return {"ok":True}

@router.delete("/users/{employee_id}/competencies/{assignment_id}")
def remove(employee_id:int,assignment_id:int,authorization:str|None=Header(default=None)):
    main.access(actor(authorization),employee_id,write=True)
    with main.database() as db:
        cur=db.execute("DELETE FROM employee_competencies WHERE id=? AND employee_id=?",
                       (assignment_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Компетенция не найдена")
    return {"ok":True}
