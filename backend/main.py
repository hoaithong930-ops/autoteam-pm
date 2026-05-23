from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3, os, uuid, json
from datetime import date

app = FastAPI(title="AutoTeam PM API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, "..", "data", "autoteam.db")
FRONT_DIR = os.path.join(BASE_DIR, "..", "frontend")

# ─── DATABASE ───────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS members (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT,
        skills TEXT,
        email TEXT,
        notes TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        client TEXT,
        description TEXT,
        start_date TEXT,
        deadline TEXT,
        leader_id TEXT,
        progress INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Chờ bắt đầu',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        project_id TEXT,
        assignee_id TEXT,
        description TEXT,
        priority TEXT DEFAULT 'Trung bình',
        status TEXT DEFAULT 'Todo',
        due_date TEXT,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(assignee_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        type TEXT,
        project_id TEXT,
        description TEXT,
        revision TEXT DEFAULT '01',
        status TEXT DEFAULT 'Draft',
        link TEXT,
        updated_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );
    """)
    conn.commit()
    conn.close()

def seed_db():
    conn = get_db()
    c = conn.cursor()
    if c.execute("SELECT COUNT(*) FROM members").fetchone()[0] > 0:
        conn.close()
        return
    today_str = str(date.today())
    members = [
        ("m1","Trần Văn Hùng","Team Leader","Siemens S7-300/400,SCADA WinCC,P&ID,Oil & Gas","hung@auto.com","10 năm kinh nghiệm Oil & Gas",today_str),
        ("m2","Nguyễn Thị Mai","SCADA Engineer","Ignition SCADA,Wonderware,HMI Design,Historian","mai@auto.com","Chuyên SCADA Power Plant",today_str),
        ("m3","Lê Minh Tuấn","PLC Programmer","Siemens S7-1500,Rockwell PLC,Function Block,Safety PLC","tuan@auto.com","Chuyên PLC Safety cho Mining",today_str),
        ("m4","Phạm Quốc Bảo","Instrumentation Engineer","HART Protocol,Foundation Fieldbus,Calibration,Loop Drawing","bao@auto.com","Instrumentation & Control",today_str),
        ("m5","Hoàng Thị Lan","Automation Engineer","ABB DCS,DeltaV,Control Strategy,SIL Assessment","lan@auto.com","DCS specialist",today_str),
        ("m6","Đặng Văn Phúc","Junior Engineer","AutoCAD,Wiring Design,PLC Basic,Commissioning","phuc@auto.com","Nhân viên mới",today_str),
    ]
    c.executemany("INSERT INTO members VALUES (?,?,?,?,?,?,?)", members)
    projects = [
        ("p1","PLC Upgrade - Wellhead Platform WHP-A","Oil & Gas","PetroVietnam E&P","Nâng cấp PLC S7-300 lên S7-1500 cho 12 giếng","2026-01-15","2026-07-30","m1",65,"Đang triển khai",today_str),
        ("p2","SCADA Control Room - Power Plant 4","Power Plant","EVN Thủ Đức","Xây dựng SCADA trung tâm 300MW","2026-02-01","2026-09-15","m2",35,"Đang triển khai",today_str),
        ("p3","Safety Shutdown System - Coal Mine","Mining","Vinacomin","Thiết kế SIS cho khai thác than hầm lò","2026-03-10","2026-12-31","m3",15,"Đang triển khai",today_str),
        ("p4","DCS Commissioning - Gas Processing Plant","Oil & Gas","PV Gas","Commissioning DCS ABB nhà máy xử lý khí","2025-10-01","2026-06-01","m5",90,"Đang triển khai",today_str),
    ]
    c.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)", projects)
    tasks = [
        ("t1","Lập trình Function Block valve control S7-1500","p1","m3","Viết FB cho 24 van WHP-A","Cao","In Progress","2026-05-28",today_str),
        ("t2","Thiết kế HMI màn hình overview platform","p1","m2","SCADA overview wellhead","Trung bình","Todo","2026-06-05",today_str),
        ("t3","Review P&ID Rev.3 và comment FAT checklist","p1","m4","","Cao","Review",today_str,today_str),
        ("t4","Cấu hình OPC-UA server kết nối DCS-SCADA","p2","m5","","Trung bình","In Progress","2026-06-10",today_str),
        ("t5","Thiết kế wiring diagram tủ MCC motor 6.6kV","p2","m6","AutoCAD Electrical","Thấp","Todo","2026-06-20",today_str),
        ("t6","SIL Assessment cho emergency shutdown system","p3","m3","","Cao","Todo","2026-07-01",today_str),
        ("t7","Calibration 45 transmitter áp suất","p4","m4","","Trung bình","Done","2026-05-15",today_str),
        ("t8","Factory Acceptance Test (FAT) DCS Cabinet","p4","m1","","Cao","Done","2026-05-10",today_str),
    ]
    c.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)", tasks)
    docs = [
        ("d1","WHP-A PLC I/O List Rev.04","P&ID","p1","Danh sách I/O đầy đủ","04","Approved","","2026-05-18"),
        ("d2","SCADA Tag Database v2.3","SCADA","p2","Database tag Power Plant 4","03","Review","","2026-05-20"),
        ("d3","SIS Logic Diagram - Gas Mine","PLC Program","p3","Logic sơ đồ an toàn hầm lò","01","Draft","","2026-05-22"),
        ("d4","DCS Wiring Drawing Package","Wiring","p4","Bản vẽ wiring DCS cabinet","02","Approved","","2026-05-01"),
        ("d5","Commissioning Manual DCS ABB","Manual","p4","Hướng dẫn commissioning","01","Approved","","2026-04-20"),
        ("d6","Weekly Progress Report W20/2026","Report","p1","Báo cáo tiến độ tuần 20","01","Approved","",today_str),
    ]
    c.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)", docs)
    conn.commit()
    conn.close()

# ─── MODELS ────────────────────────────────────────────────
class MemberIn(BaseModel):
    name: str
    role: Optional[str] = ""
    skills: Optional[str] = ""
    email: Optional[str] = ""
    notes: Optional[str] = ""

class ProjectIn(BaseModel):
    name: str
    type: Optional[str] = "Oil & Gas"
    client: Optional[str] = ""
    description: Optional[str] = ""
    start_date: Optional[str] = ""
    deadline: Optional[str] = ""
    leader_id: Optional[str] = ""
    progress: Optional[int] = 0
    status: Optional[str] = "Chờ bắt đầu"

class TaskIn(BaseModel):
    title: str
    project_id: Optional[str] = ""
    assignee_id: Optional[str] = ""
    description: Optional[str] = ""
    priority: Optional[str] = "Trung bình"
    status: Optional[str] = "Todo"
    due_date: Optional[str] = ""

class DocumentIn(BaseModel):
    name: str
    type: Optional[str] = "Khác"
    project_id: Optional[str] = ""
    description: Optional[str] = ""
    revision: Optional[str] = "01"
    status: Optional[str] = "Draft"
    link: Optional[str] = ""

# ─── MEMBERS ───────────────────────────────────────────────
@app.get("/api/members")
def list_members():
    conn = get_db()
    rows = conn.execute("SELECT * FROM members ORDER BY created_at").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/members", status_code=201)
def create_member(m: MemberIn):
    conn = get_db()
    mid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO members VALUES (?,?,?,?,?,?,?)",
        (mid, m.name, m.role, m.skills, m.email, m.notes, str(date.today())))
    conn.commit(); conn.close()
    return {"id": mid}

@app.put("/api/members/{mid}")
def update_member(mid: str, m: MemberIn):
    conn = get_db()
    conn.execute("UPDATE members SET name=?,role=?,skills=?,email=?,notes=? WHERE id=?",
        (m.name, m.role, m.skills, m.email, m.notes, mid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/members/{mid}")
def delete_member(mid: str):
    conn = get_db()
    conn.execute("DELETE FROM members WHERE id=?", (mid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── PROJECTS ──────────────────────────────────────────────
@app.get("/api/projects")
def list_projects():
    conn = get_db()
    rows = conn.execute("""
        SELECT p.*, m.name as leader_name
        FROM projects p LEFT JOIN members m ON p.leader_id=m.id
        ORDER BY p.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/projects", status_code=201)
def create_project(p: ProjectIn):
    conn = get_db()
    pid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (pid, p.name, p.type, p.client, p.description,
         p.start_date, p.deadline, p.leader_id, p.progress, p.status, str(date.today())))
    conn.commit(); conn.close()
    return {"id": pid}

@app.put("/api/projects/{pid}")
def update_project(pid: str, p: ProjectIn):
    conn = get_db()
    conn.execute("""UPDATE projects SET name=?,type=?,client=?,description=?,
        start_date=?,deadline=?,leader_id=?,progress=?,status=? WHERE id=?""",
        (p.name, p.type, p.client, p.description,
         p.start_date, p.deadline, p.leader_id, p.progress, p.status, pid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/projects/{pid}")
def delete_project(pid: str):
    conn = get_db()
    conn.execute("DELETE FROM projects WHERE id=?", (pid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── TASKS ─────────────────────────────────────────────────
@app.get("/api/tasks")
def list_tasks():
    conn = get_db()
    rows = conn.execute("""
        SELECT t.*, m.name as assignee_name, p.name as project_name
        FROM tasks t
        LEFT JOIN members m ON t.assignee_id=m.id
        LEFT JOIN projects p ON t.project_id=p.id
        ORDER BY t.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/tasks", status_code=201)
def create_task(t: TaskIn):
    conn = get_db()
    tid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",
        (tid, t.title, t.project_id, t.assignee_id,
         t.description, t.priority, t.status, t.due_date, str(date.today())))
    conn.commit(); conn.close()
    return {"id": tid}

@app.put("/api/tasks/{tid}")
def update_task(tid: str, t: TaskIn):
    conn = get_db()
    conn.execute("""UPDATE tasks SET title=?,project_id=?,assignee_id=?,description=?,
        priority=?,status=?,due_date=? WHERE id=?""",
        (t.title, t.project_id, t.assignee_id, t.description,
         t.priority, t.status, t.due_date, tid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/tasks/{tid}")
def delete_task(tid: str):
    conn = get_db()
    conn.execute("DELETE FROM tasks WHERE id=?", (tid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── DOCUMENTS ─────────────────────────────────────────────
@app.get("/api/documents")
def list_documents():
    conn = get_db()
    rows = conn.execute("""
        SELECT d.*, p.name as project_name
        FROM documents d LEFT JOIN projects p ON d.project_id=p.id
        ORDER BY d.updated_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/documents", status_code=201)
def create_document(d: DocumentIn):
    conn = get_db()
    did = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)",
        (did, d.name, d.type, d.project_id, d.description,
         d.revision, d.status, d.link, str(date.today())))
    conn.commit(); conn.close()
    return {"id": did}

@app.put("/api/documents/{did}")
def update_document(did: str, d: DocumentIn):
    conn = get_db()
    conn.execute("""UPDATE documents SET name=?,type=?,project_id=?,description=?,
        revision=?,status=?,link=?,updated_at=? WHERE id=?""",
        (d.name, d.type, d.project_id, d.description,
         d.revision, d.status, d.link, str(date.today()), did))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/documents/{did}")
def delete_document(did: str):
    conn = get_db()
    conn.execute("DELETE FROM documents WHERE id=?", (did,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── DASHBOARD STATS ───────────────────────────────────────
@app.get("/api/stats")
def get_stats():
    conn = get_db()
    c = conn.cursor()
    return {
        "projects":  c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
        "tasks_done": c.execute("SELECT COUNT(*) FROM tasks WHERE status='Done'").fetchone()[0],
        "tasks_open": c.execute("SELECT COUNT(*) FROM tasks WHERE status!='Done'").fetchone()[0],
        "members":   c.execute("SELECT COUNT(*) FROM members").fetchone()[0],
        "tasks_today": c.execute(
            "SELECT COUNT(*) FROM tasks WHERE due_date=? AND status!='Done'",
            (str(date.today()),)).fetchone()[0],
    }

# ─── SERVE FRONTEND ────────────────────────────────────────
if os.path.exists(FRONT_DIR):
    app.mount("/static", StaticFiles(directory=FRONT_DIR, html=True), name="static")

@app.get("/", include_in_schema=False)
def root():
    index = os.path.join(FRONT_DIR, "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "AutoTeam PM API running. Place frontend in /frontend/index.html"}

# ─── STARTUP ───────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    seed_db()
    print("✅ AutoTeam PM Server ready at http://localhost:8000")
