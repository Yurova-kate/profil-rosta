"""Career and detailed project history; additive migrations preserve legacy projects."""
import sqlite3
from datetime import date
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field, model_validator
from . import main

router = APIRouter(prefix="/api")
class WorkEntry(BaseModel):
    company: str = Field(min_length=2,max_length=180)
    position: str = Field(min_length=2,max_length=180)
    start_date: date
    end_date: date | None = None
    current: bool = False
    description: str = Field(default="",max_length=4000)
    achievements: str = Field(default="",max_length=4000)
    @model_validator(mode="after")
    def dates_valid(self):
        if self.end_date and self.end_date < self.start_date:
            raise ValueError("Дата окончания раньше даты начала")
        if self.current and self.end_date:
            raise ValueError("Для текущего места работы не указывайте дату окончания")
        return self

class ProjectEntry(BaseModel):
    title: str = Field(min_length=2,max_length=200)
    description: str = Field(default="",max_length=4000)
    role: str = Field(default="",max_length=180)
    organization: str = Field(default="",max_length=180)
    start_date: date | None = None
    end_date: date | None = None
    technologies: str = Field(default="",max_length=1200)
    outcomes: str = Field(default="",max_length=4000)
    work_experience_id: int | None = None
    @model_validator(mode="after")
    def dates_valid(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("Дата завершения проекта раньше даты начала")
        return self

def initialize():
    with main.database() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS work_experiences(
            id INTEGER PRIMARY KEY,
            employee_id INTEGER NOT NULL REFERENCES users(id),
            company TEXT NOT NULL,
            position TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT,
            current INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            achievements TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)""")
        existing={r["name"] for r in db.execute("PRAGMA table_info(projects)")}
        for col,definition in {
            "role":"TEXT NOT NULL DEFAULT ''",
            "organization":"TEXT NOT NULL DEFAULT ''",
            "start_date":"TEXT",
            "end_date":"TEXT",
            "technologies":"TEXT NOT NULL DEFAULT ''",
            "outcomes":"TEXT NOT NULL DEFAULT ''",
            "work_experience_id":"INTEGER REFERENCES work_experiences(id)"
        }.items():
            if col not in existing:
                db.execute(f"ALTER TABLE projects ADD COLUMN {col} {definition}")

def check_employer(db,employee_id,work_id):
    if work_id is not None and not db.execute(
        "SELECT id FROM work_experiences WHERE id=? AND employee_id=?",(work_id,employee_id)).fetchone():
        raise HTTPException(422,"Место работы не принадлежит сотруднику")

@router.get("/users/{employee_id}/career")
def career(employee_id:int,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id)
    with main.database() as db:
        work=[dict(r) for r in db.execute(
            "SELECT * FROM work_experiences WHERE employee_id=? ORDER BY current DESC,start_date DESC,id DESC",(employee_id,))]
        projects=[dict(r) for r in db.execute(
            "SELECT * FROM projects WHERE employee_id=? ORDER BY start_date IS NULL,start_date DESC,id DESC",(employee_id,))]
        return {"work_experiences":work,"projects":projects}

@router.post("/users/{employee_id}/work-experiences")
def add_work(employee_id:int,data:WorkEntry,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        cur=db.execute("""INSERT INTO work_experiences
        (employee_id,company,position,start_date,end_date,current,description,achievements)
        VALUES(?,?,?,?,?,?,?,?)""",(employee_id,data.company.strip(),data.position.strip(),
        data.start_date.isoformat(),data.end_date.isoformat() if data.end_date else None,
        int(data.current),data.description.strip(),data.achievements.strip()))
        return {"id":cur.lastrowid}

@router.put("/users/{employee_id}/work-experiences/{entry_id}")
def edit_work(employee_id:int,entry_id:int,data:WorkEntry,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        cur=db.execute("""UPDATE work_experiences SET company=?,position=?,start_date=?,
          end_date=?,current=?,description=?,achievements=? WHERE id=? AND employee_id=?""",
          (data.company.strip(),data.position.strip(),data.start_date.isoformat(),
           data.end_date.isoformat() if data.end_date else None,int(data.current),
           data.description.strip(),data.achievements.strip(),entry_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Место работы не найдено")
        return {"ok":True}

@router.delete("/users/{employee_id}/work-experiences/{entry_id}")
def delete_work(employee_id:int,entry_id:int,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        db.execute("UPDATE projects SET work_experience_id=NULL WHERE employee_id=? AND work_experience_id=?",(employee_id,entry_id))
        cur=db.execute("DELETE FROM work_experiences WHERE employee_id=? AND id=?",(employee_id,entry_id))
        if not cur.rowcount: raise HTTPException(404,"Место работы не найдено")
        return {"ok":True}

@router.post("/users/{employee_id}/career/projects")
def add_project(employee_id:int,data:ProjectEntry,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        check_employer(db,employee_id,data.work_experience_id)
        cur=db.execute("""INSERT INTO projects
         (employee_id,title,description,role,organization,start_date,end_date,technologies,outcomes,work_experience_id)
         VALUES(?,?,?,?,?,?,?,?,?,?)""",
         (employee_id,data.title.strip(),data.description.strip(),data.role.strip(),
          data.organization.strip(),data.start_date.isoformat() if data.start_date else None,
          data.end_date.isoformat() if data.end_date else None,data.technologies.strip(),
          data.outcomes.strip(),data.work_experience_id))
        return {"id":cur.lastrowid}

@router.put("/users/{employee_id}/career/projects/{project_id}")
def edit_project(employee_id:int,project_id:int,data:ProjectEntry,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        check_employer(db,employee_id,data.work_experience_id)
        cur=db.execute("""UPDATE projects SET title=?,description=?,role=?,organization=?,
        start_date=?,end_date=?,technologies=?,outcomes=?,work_experience_id=?
        WHERE id=? AND employee_id=?""",
        (data.title.strip(),data.description.strip(),data.role.strip(),data.organization.strip(),
         data.start_date.isoformat() if data.start_date else None,
         data.end_date.isoformat() if data.end_date else None,data.technologies.strip(),
         data.outcomes.strip(),data.work_experience_id,project_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Проект не найден")
        return {"ok":True}

@router.delete("/users/{employee_id}/career/projects/{project_id}")
def delete_project(employee_id:int,project_id:int,authorization:str|None=Header(default=None)):
    main.access(main.current(authorization),employee_id,write=True)
    with main.database() as db:
        cur=db.execute("DELETE FROM projects WHERE id=? AND employee_id=?",(project_id,employee_id))
        if not cur.rowcount: raise HTTPException(404,"Проект не найден")
        return {"ok":True}
