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
            goal=call("POST",f"/api/users/{employee_id}/development",token,{"title":"Освоить компетенцию","competency_id":competency_id,"target_level":"expert","actions":"Практика и обучение"}).json()["id"]
            goals=call("GET",f"/api/users/{employee_id}/development",token).json()
            assert goals[0]["id"]==goal
            assert call("GET",f"/api/users/{employee_id}/competencies",token).json()==[]
            assert call("PUT",f"/api/users/{employee_id}/development/{goal}",token,{"title":"Освоить компетенцию","competency_id":competency_id,"target_level":"advanced","status":"completed"}).status_code==200
            assert call("GET",f"/api/users/{employee_id}/competencies",token).json()==[]
            assert call("DELETE",f"/api/users/{employee_id}/development/{goal}",token).status_code==200
