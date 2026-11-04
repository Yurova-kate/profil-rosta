from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app import main
from app.server import app

def test_development_goals_do_not_change_skills():
    with TemporaryDirectory() as folder:
        main.DB=Path(folder)/"test.db"
        with TestClient(app) as client:
            def call(method,path,token=None,data=None):
                return client.request(method,path,headers={"Authorization":f"Bearer {token}"} if token else {},json=data)
            assert call("POST","/api/bootstrap",data={"name":"Admin","email":"admin@demo.local","password":"password0001"}).status_code==200
            token=call("POST","/api/login",data={"email":"admin@demo.local","password":"password0001"}).json()["token"]
            me=call("GET","/api/me",token).json()
            employee_id=me["id"]
            catalog=call("GET","/api/competencies/catalog",token).json()
            assert catalog
            competency_id=catalog[0]["id"]
            certification=call("POST","/api/certifications",token,{"skill_keyword":"СКД","exam_title":"Учебный экзамен"}).json()["id"]
            goal=call("POST",f"/api/users/{employee_id}/development",token,{"title":"Освоить компетенцию","competency_id":competency_id,"target_level":"expert","certification_id":certification,"actions":"Практика и обучение"}).json()["id"]
            goals=call("GET",f"/api/users/{employee_id}/development",token).json()
            assert goals[0]["id"]==goal
            assert goals[0]["certification_id"]==certification
            assert goals[0]["certification_name"]=="Учебный экзамен"
            assert call("GET",f"/api/users/{employee_id}/competencies",token).json()==[]
            assert call("PUT",f"/api/users/{employee_id}/development/{goal}",token,{"title":"Освоить компетенцию","competency_id":competency_id,"target_level":"advanced","status":"completed"}).status_code==200
            updated=call("GET",f"/api/users/{employee_id}/development",token).json()[0]
            assert updated["status"]=="completed"
            assert updated["certification_id"] is None
            assert call("POST",f"/api/users/{employee_id}/development",token,{"title":"Некорректная цель","certification_id":999999}).status_code==404
            assert call("GET",f"/api/users/{employee_id}/competencies",token).json()==[]
            assert call("DELETE",f"/api/users/{employee_id}/development/{goal}",token).status_code==200
