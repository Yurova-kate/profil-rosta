from pathlib import Path
from tempfile import TemporaryDirectory
from fastapi.testclient import TestClient
from app import main
from app.server import app

def test_catalog_permissions_and_self_assessment():
    with TemporaryDirectory() as folder:
        main.DB=Path(folder)/"test.db"
        with TestClient(app) as client:
            def req(method,path,token=None,body=None):
                return client.request(method,path,headers={"Authorization":"Bearer "+token} if token else {},json=body)
            assert req("POST","/api/bootstrap",body={"name":"Admin","email":"admin@demo.local","password":"password0001"}).status_code==200
            def login(email,password):
                return req("POST","/api/login",body={"email":email,"password":password}).json()["token"]
            admin=login("admin@demo.local","password0001")
            manager_id=req("POST","/api/users",admin,{"name":"Manager","email":"manager@demo.local","password":"password0002","role":"manager"}).json()["id"]
            employee_id=req("POST","/api/users",admin,{"name":"Employee","email":"employee@demo.local","password":"password0003","role":"employee","manager_id":manager_id}).json()["id"]
            manager=login("manager@demo.local","password0002")
            employee=login("employee@demo.local","password0003")
            item={"name":"Система компоновки данных","category":"Платформа 1С"}
            assert req("POST","/api/competencies/catalog",employee,item).status_code==403
            competency_id=req("POST","/api/competencies/catalog",admin,item).json()["id"]
            assert req("POST","/api/competencies/catalog",admin,item).status_code==409
            assignment_id=req("POST",f"/api/users/{employee_id}/competencies",employee,{"competency_id":competency_id,"level":"intermediate"}).json()["id"]
            assert req("POST",f"/api/users/{employee_id}/competencies",employee,{"competency_id":competency_id,"level":"advanced"}).status_code==409
            assert req("POST",f"/api/users/{employee_id}/competencies/{assignment_id}/confirm",manager).status_code==405
            assert req("PUT",f"/api/users/{employee_id}/competencies/{assignment_id}",manager,{"level":"expert"}).status_code==403
            assert req("PUT",f"/api/users/{employee_id}/competencies/{assignment_id}",employee,{"level":"advanced"}).status_code==200
            records=req("GET",f"/api/users/{employee_id}/competencies",employee).json()
            assert records[0]["level"]=="advanced"
            assert "verified_by" not in records[0]
            old_skill=req("POST",f"/api/users/{employee_id}/skills",employee,{"name":"СКД"}).json()["id"]
            assert req("POST",f"/api/users/{employee_id}/competencies/map-legacy",manager,{"skill_id":old_skill,"competency_id":competency_id,"level":"intermediate"}).status_code==403
            assert req("POST",f"/api/users/{employee_id}/competencies/map-legacy",employee,{"skill_id":old_skill,"competency_id":competency_id,"level":"intermediate"}).status_code==409
            assert req("DELETE",f"/api/users/{employee_id}/competencies/{assignment_id}",employee).status_code==200
            mapped=req("POST",f"/api/users/{employee_id}/competencies/map-legacy",employee,{"skill_id":old_skill,"competency_id":competency_id,"level":"advanced"})
            assert mapped.status_code==200 and mapped.json()["source_preserved"] is True
            assert req("POST",f"/api/users/{employee_id}/competencies/map-legacy",employee,{"skill_id":old_skill,"competency_id":competency_id,"level":"advanced"}).status_code==409
            assert req("GET",f"/api/users/{employee_id}/profile",employee).json()["skills"][0]["name"]=="СКД"

