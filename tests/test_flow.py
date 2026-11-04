import os, tempfile
from fastapi.testclient import TestClient
from app import main

def test_end_to_end():
    with tempfile.TemporaryDirectory() as folder:
        main.DB=__import__("pathlib").Path(folder)/"test.db"
        with TestClient(main.app) as client:
            def call(method,path,token=None,**kwargs):
                return getattr(client,method)(path,headers={"Authorization":f"Bearer {token}"} if token else {},**kwargs)
            assert call("post","/api/bootstrap",json={"email":"admin@test.local","name":"Администратор","password":"securepassword1"}).status_code==200
            a=call("post","/api/login",json={"email":"admin@test.local","password":"securepassword1"}).json()["token"]
            m=call("post","/api/users",a,json={"email":"manager@test.local","name":"Руководитель","password":"securepassword2","role":"manager"}).json()["id"]
            e=call("post","/api/users",a,json={"email":"employee@test.local","name":"Сотрудник","password":"securepassword3","role":"employee","manager_id":m}).json()["id"]
            mt=call("post","/api/login",json={"email":"manager@test.local","password":"securepassword2"}).json()["token"]
            et=call("post","/api/login",json={"email":"employee@test.local","password":"securepassword3"}).json()["token"]
            s=call("post",f"/api/users/{e}/skills",et,json={"name":"СКД 1С"}).json()["id"]
            assert call("post",f"/api/users/{e}/skills/{s}/confirm",et).status_code==403
            assert call("post",f"/api/users/{e}/skills/{s}/confirm",mt).status_code==200
            assert call("post",f"/api/users/{e}/projects",et,json={"title":"Внедрение 1С","description":"Разработка отчётов"}).status_code==200
            assert call("post","/api/certifications",a,json={"skill_keyword":"СКД","exam_title":"Учебный экзамен 1С"}).status_code==200
            p=call("get",f"/api/users/{e}/profile",et).json()
            assert p["skills"][0]["verified_by"]==m
            assert p["certifications"][0]["exam_title"]=="Учебный экзамен 1С"
            r=call("get",f"/api/users/{e}/resume.docx",et)
            assert r.status_code==200 and r.content[:2]==b"PK"
            assert call("get",f"/api/users/{m}/profile",et).status_code==403
