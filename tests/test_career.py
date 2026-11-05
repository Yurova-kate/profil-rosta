"""Regression tests for career history and detailed project records."""
from pathlib import Path
from tempfile import TemporaryDirectory
from io import BytesIO
from docx import Document
from fastapi.testclient import TestClient
from app import main
from app.server import app

def test_multiple_jobs_projects_permissions_and_docx():
    with TemporaryDirectory() as temp:
        main.DB=Path(temp)/"career.db"
        with TestClient(app) as client:
            def req(method,path,token=None,data=None):
                return client.request(method,path,headers={"Authorization":"Bearer "+token} if token else {},json=data)
            assert req("POST","/api/bootstrap",data={"name":"Admin","email":"admin@career.test","password":"password0001"}).status_code==200
            admin=req("POST","/api/login",data={"email":"admin@career.test","password":"password0001"}).json()["token"]
            mgr=req("POST","/api/users",admin,{"name":"Manager","email":"manager@career.test","password":"password0002","role":"manager"}).json()["id"]
            employee=req("POST","/api/users",admin,{"name":"Employee","email":"employee@career.test","password":"password0003","role":"employee","manager_id":mgr}).json()["id"]
            own=req("POST","/api/login",data={"email":"employee@career.test","password":"password0003"}).json()["token"]
            manager=req("POST","/api/login",data={"email":"manager@career.test","password":"password0002"}).json()["token"]
            base=f"/api/users/{employee}"
            a=req("POST",base+"/work-experiences",own,{"company":"Alpha","position":"Аналитик 1С","start_date":"2022-01-01","end_date":"2023-02-01"});assert a.status_code==200,a.text
            first=a.json()["id"]
            b=req("POST",base+"/work-experiences",own,{"company":"Beta","position":"Ведущий аналитик","start_date":"2023-02-02","current":True,"achievements":"Сократили время обработки на 20%"});assert b.status_code==200,b.text
            second=b.json()["id"]
            assert req("POST",base+"/work-experiences",own,{"company":"Invalid","position":"Dev","start_date":"2024-01-01","end_date":"2022-01-01"}).status_code==422
            assert req("POST",base+"/work-experiences",manager,{"company":"Forbidden","position":"Role","start_date":"2024-01-01"}).status_code==403
            p=req("POST",base+"/career/projects",own,{"title":"1С:ЗУП","role":"Аналитик","start_date":"2023-04-01","work_experience_id":second,"technologies":"СКД","outcomes":"Запуск в эксплуатацию"})
            assert p.status_code==200,p.text
            project=p.json()["id"]
            legacy=req("POST",base+"/projects",own,{"title":"Старый проект","description":"Перенесён без потерь"})
            assert legacy.status_code==200,legacy.text
            data=req("GET",base+"/career",own).json()
            assert len(data["work_experiences"])==2
            assert len(data["projects"])==2
            assert data["projects"][0]["role"]=="Аналитик"
            assert req("GET",base+"/career",manager).status_code==200
            assert req("PUT",base+f"/career/projects/{project}",manager,{"title":"Не менять"}).status_code==403
            assert req("PUT",base+f"/career/projects/{project}",own,{"title":"1С:ЗУП","role":"Ведущий аналитик","outcomes":"Автоматизация"}).status_code==200
            assert req("POST",base+"/career/projects",own,{"title":"Некорректная связь","work_experience_id":99999}).status_code==422
            doc=req("GET",base+"/resume.docx",own)
            assert doc.status_code==200
            paragraphs="\n".join(p.text for p in Document(BytesIO(doc.content)).paragraphs)
            for fragment in ["Alpha","Beta","Ведущий аналитик","1С:ЗУП","Автоматизация","Старый проект"]:
                assert fragment in paragraphs
            assert req("DELETE",base+f"/work-experiences/{second}",own).status_code==200
            data=req("GET",base+"/career",own).json()
            assert data["projects"][0]["work_experience_id"] is None
            assert len(data["work_experiences"])==1
            assert req("DELETE",base+f"/career/projects/{project}",own).status_code==200
            assert len(req("GET",base+"/career",own).json()["projects"])==1
            assert req("GET",f"/api/users/{mgr}/career",own).status_code==403
