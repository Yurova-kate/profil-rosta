"""Employee-owned professional development goals. Goals never mutate actual skills."""
import sqlite3
from datetime import date
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field
from . import main

router=APIRouter(prefix="/api")
LEVELS={"beginner","intermediate","advanced","expert"}
STATUSES={"planned","in_progress","completed","cancelled"}

class GoalCreate(BaseModel):
    title:str=Field(min_length=3,max_length=180)
    competency_id:int|None=None
    target_level:str|None=None
    certification_id:int|None=None
    due_date:date|None=None
    actions:str=Field(default="",max_length=3000)

class GoalUpdate(GoalCreate):
    status:str="planned"

def initialize():
    with main.database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS development_goals(
            id INTEGER PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            title TEXT NOT NULL,
            competency_id INTEGER REFERENCES competency_catalog(id),
            target_level TEXT,
            certification_id INTEGER REFERENCES certifications(id),
            due_date TEXT,
            actions TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL DEFAULT 'planned',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        if "certification_id" not in {r["name"] for r in db.execute("PRAGMA table_info(development_goals)")}:
            db.execute("ALTER TABLE development_goals ADD COLUMN certification_id INTEGER REFERENCES certifications(id)")

def check(data):
    if not data.title.strip(): raise HTTPException(422,"Укажите цель")
    if data.target_level is not None and data.target_level not in LEVELS:
        raise HTTPException(422,"Некорректный целевой уровень")
    if data.target_level and not data.competency_id:
        raise HTTPException(422,"Для целевого уровня выберите компетенцию")
    if isinstance(data,GoalUpdate) and data.status not in STATUSES:
        raise HTTPException(422,"Некорректный статус")

def validate_competency(db,competency_id,certification_id=None):
    if certification_id is not None and not db.execute("SELECT 1 FROM certifications WHERE id=?",(certification_id,)).fetchone():
        raise HTTPException(404,"Сертификация не найдена")
    if competency_id is not None and not db.execute(
        "SELECT 1 FROM competency_catalog WHERE id=? AND active=1",(competency_id,)).fetchone():
        raise HTTPException(404,"Компетенция не найдена")

@router.get("/users/{employee_id}/development")
def list_goals(employee_id:int,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id)
    with main.database() as db:
        return [dict(row) for row in db.execute("""SELECT g.id,g.title,g.competency_id,
            c.name AS competency_name,g.target_level,g.certification_id,cert.exam_title AS certification_name,g.due_date,g.actions,g.status,
            g.created_at,g.updated_at
            FROM development_goals g LEFT JOIN competency_catalog c ON c.id=g.competency_id
            LEFT JOIN certifications cert ON cert.id=g.certification_id
            WHERE g.employee_id=? ORDER BY
            CASE g.status WHEN 'in_progress' THEN 0 WHEN 'planned' THEN 1 ELSE 2 END,
            g.due_date IS NULL,g.due_date,g.id""",(employee_id,))]

@router.post("/users/{employee_id}/development")
def create_goal(employee_id:int,data:GoalCreate,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    check(data)
    with main.database() as db:
        validate_competency(db,data.competency_id,data.certification_id)
        try:
            cur=db.execute("""INSERT INTO development_goals(
                employee_id,title,competency_id,target_level,certification_id,due_date,actions)
                VALUES(?,?,?,?,?,?,?)""",(employee_id,data.title.strip(),data.competency_id,
                data.target_level,data.certification_id,data.due_date.isoformat() if data.due_date else None,data.actions.strip()))
        except sqlite3.IntegrityError: raise HTTPException(422,"Некорректные данные")
        return {"id":cur.lastrowid}

@router.put("/users/{employee_id}/development/{goal_id}")
def update_goal(employee_id:int,goal_id:int,data:GoalUpdate,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    check(data)
    with main.database() as db:
        validate_competency(db,data.competency_id)
        cur=db.execute("""UPDATE development_goals SET title=?,competency_id=?,target_level=?,
            certification_id=?,due_date=?,actions=?,status=?,updated_at=CURRENT_TIMESTAMP
            WHERE id=? AND employee_id=?""",(data.title.strip(),data.competency_id,data.target_level,
            data.due_date.isoformat() if data.due_date else None,data.actions.strip(),
            data.status,goal_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Цель не найдена")
    return {"ok":True}

@router.delete("/users/{employee_id}/development/{goal_id}")
def delete_goal(employee_id:int,goal_id:int,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        cur=db.execute("DELETE FROM development_goals WHERE id=? AND employee_id=?",(goal_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Цель не найдена")
    return {"ok":True}
