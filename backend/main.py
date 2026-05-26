from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3, os, uuid, json, shutil
from datetime import date, datetime, timedelta

import hashlib, secrets

# ─── RBAC: ROLES (tài liệu Mục 3.4) ───
ROLES = {
    "super_admin":  {"name": "Super Admin",         "level": 100},
    "admin":        {"name": "Admin",               "level": 90},
    "manager":      {"name": "Manager",             "level": 80},
    "pm":           {"name": "Project Manager",     "level": 70},
    "lead":         {"name": "Lead Engineer",       "level": 60},
    "engineer":     {"name": "Automation Engineer", "level": 50},
    "doc_control":  {"name": "Document Controller", "level": 50},
    "procurement":  {"name": "Procurement",         "level": 50},
    "viewer":       {"name": "Viewer",              "level": 10},
}

# ─── RBAC: PERMISSION MATRIX (tài liệu Mục 3.5) ───
PERMISSION_MATRIX = {
    "super_admin": {"dashboard":"full","project":"full","task":"full","material":"full","bom":"full","document":"full","report":"full","user_mgmt":"full","inventory":"full"},
    "admin":       {"dashboard":"full","project":"full","task":"full","material":"full","bom":"full","document":"full","report":"full","user_mgmt":"full","inventory":"full"},
    "manager":     {"dashboard":"full","project":"full","task":"full","material":"view","bom":"full","document":"full","report":"full","user_mgmt":"view","inventory":"view"},
    "pm":          {"dashboard":"full","project":"edit","task":"create","material":"view","bom":"edit","document":"edit","report":"edit","user_mgmt":"none","inventory":"view"},
    "lead":        {"dashboard":"view","project":"edit","task":"create","material":"edit","bom":"edit","document":"edit","report":"view","user_mgmt":"none","inventory":"edit"},
    "engineer":    {"dashboard":"view","project":"view","task":"edit","material":"view","bom":"edit","document":"edit","report":"view","user_mgmt":"none","inventory":"view"},
    "doc_control": {"dashboard":"view","project":"view","task":"view","material":"view","bom":"view","document":"full","report":"view","user_mgmt":"none","inventory":"view"},
    "procurement": {"dashboard":"view","project":"view","task":"view","material":"edit","bom":"edit","document":"view","report":"view","user_mgmt":"none","inventory":"full"},
    "viewer":      {"dashboard":"view","project":"view","task":"view","material":"view","bom":"view","document":"view","report":"view","user_mgmt":"none","inventory":"view"},
}

def hash_password(password, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000).hex()
    return salt + "$" + h

def verify_password(password, stored):
    try:
        salt, _ = stored.split("$", 1)
        return hash_password(password, salt) == stored
    except:
        return False

def make_token():
    return secrets.token_urlsafe(32)

def date_duration(start, finish):
    try:
        if not start or not finish:
            return 0
        return max(0, (date.fromisoformat(str(finish)[:10]) - date.fromisoformat(str(start)[:10])).days + 1)
    except:
        return 0


APP_VERSION = "2.4.3"
APP_RELEASE_DATE = "2026-05-25"
APP_BUILD_LABEL = "wireframe-task-treegrid"
APP_CHANGELOG = [
    "Updated Tasks to wireframe-style TreeGrid with detail tool panel.",
    "Added WBS code, parent id, and duration fields for schedule hierarchy.",
    "Redesigned Tasks as a Project > Phase > Work Group > Task schedule.",
    "Added create, edit, and delete APIs for project phases.",
    "Added E-Office latest 10 emails per person from Email Log.",
    "Expanded auth with profile, password reset demo, lockout, and session timeout.",
    "Added task checklist/progress/reviewer/approver, comments, and history.",
    "Added chat, document revision/comment/transmittal, RFQ/quotation/delivery, timesheet, and backup modules.",
]


app = FastAPI(title="AutoTeam PM API", version=APP_VERSION)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "..", "data", "autoteam.db")
FRONT_DIR = os.path.join(BASE_DIR, "..", "frontend")
BACKUP_DIR = os.path.join(BASE_DIR, "..", "data", "backups")
SESSION_TIMEOUT_MINUTES = 240
MAX_FAILED_LOGIN = 5

PHASES = ["Budget Approval","Bidding / Tender","EPC Contract","Engineering / Design","Procurement","Construction","Commissioning","Handover / Close-out"]

ITEM_CATEGORIES = [
    "Tủ điện / Panel",
    "Dây cáp & Phụ kiện",
    "PLC / I/O Module",
    "HMI / SCADA Hardware",
    "Thiết bị đo lường",
    "CB / MCB / MCCB / Relay",
    "Terminal Block / Cầu đấu",
    "Switch / Contactor / VFD",
    "Máy biến áp / UPS",
    "Phụ kiện cáp",
    "Khác",
]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = get_db(); c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS members (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT, skills TEXT,
        email TEXT, notes TEXT, created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT, client TEXT,
        description TEXT, start_date TEXT, deadline TEXT, leader_id TEXT,
        progress INTEGER DEFAULT 0, status TEXT DEFAULT 'Cho bat dau',
        current_phase TEXT DEFAULT 'Budget Approval',
        phase_notes TEXT DEFAULT '{}', created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY, title TEXT NOT NULL, project_id TEXT,
        assignee_id TEXT, description TEXT, priority TEXT DEFAULT 'Trung binh',
        status TEXT DEFAULT 'Todo', due_date TEXT, created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(assignee_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS documents (
        id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT, project_id TEXT,
        description TEXT, revision TEXT DEFAULT '01', status TEXT DEFAULT 'Draft',
        link TEXT, updated_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        username TEXT UNIQUE,
        password_hash TEXT NOT NULL,
        phone TEXT,
        department TEXT,
        position TEXT,
        skills TEXT,
        role TEXT DEFAULT 'engineer',
        status TEXT DEFAULT 'pending',
        avatar_color TEXT,
        last_login_at TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT,
        expires_at TEXT
    );
    CREATE TABLE IF NOT EXISTS login_history (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        email TEXT,
        ip TEXT,
        status TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_logs (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        user_name TEXT,
        action TEXT,
        module TEXT,
        detail TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS app_update_logs (
        id TEXT PRIMARY KEY,
        version TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        changed_files TEXT,
        status TEXT DEFAULT 'Released',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS inventory_items (
        id TEXT PRIMARY KEY,
        item_code TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        description TEXT,
        unit TEXT DEFAULT 'cai',
        specs TEXT,
        tags TEXT,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS inventory_vendors (
        id TEXT PRIMARY KEY,
        item_id TEXT NOT NULL,
        brand TEXT NOT NULL,
        model_no TEXT,
        origin TEXT,
        unit_price REAL DEFAULT 0,
        currency TEXT DEFAULT 'USD',
        lead_time TEXT,
        datasheet_link TEXT,
        notes TEXT,
        is_preferred INTEGER DEFAULT 0,
        created_at TEXT,
        FOREIGN KEY(item_id) REFERENCES inventory_items(id)
    );
    CREATE TABLE IF NOT EXISTS work_groups (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_name TEXT NOT NULL,
        group_name TEXT NOT NULL,
        owner_id TEXT,
        start_date TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'Not Started',
        progress INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(owner_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS project_phases (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL,
        phase_name TEXT NOT NULL,
        start_date TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'Planned',
        progress INTEGER DEFAULT 0,
        display_order INTEGER DEFAULT 0,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );
    CREATE TABLE IF NOT EXISTS issues (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        title TEXT NOT NULL,
        severity TEXT DEFAULT 'Medium',
        owner_id TEXT,
        status TEXT DEFAULT 'Open',
        due_date TEXT,
        mitigation TEXT,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(owner_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS notifications (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        title TEXT NOT NULL,
        message TEXT,
        notification_type TEXT DEFAULT 'system',
        related_module TEXT,
        related_id TEXT,
        is_read INTEGER DEFAULT 0,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS bom_headers (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        bom_no TEXT NOT NULL,
        revision TEXT DEFAULT 'A',
        title TEXT,
        status TEXT DEFAULT 'Draft',
        currency TEXT DEFAULT 'VND',
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id)
    );
    CREATE TABLE IF NOT EXISTS bom_items (
        id TEXT PRIMARY KEY,
        bom_id TEXT NOT NULL,
        material_id TEXT,
        item_no TEXT,
        description TEXT,
        qty REAL DEFAULT 1,
        unit TEXT DEFAULT 'cai',
        unit_price REAL DEFAULT 0,
        currency TEXT DEFAULT 'VND',
        supplier TEXT,
        lead_time TEXT,
        status TEXT DEFAULT 'Need Check',
        remark TEXT,
        FOREIGN KEY(bom_id) REFERENCES bom_headers(id),
        FOREIGN KEY(material_id) REFERENCES inventory_items(id)
    );
    CREATE TABLE IF NOT EXISTS eoffice_docs (
        id TEXT PRIMARY KEY,
        direction TEXT DEFAULT 'Incoming',
        doc_no TEXT,
        title TEXT NOT NULL,
        project_id TEXT,
        sender TEXT,
        receiver TEXT,
        owner_id TEXT,
        status TEXT DEFAULT 'Draft',
        due_date TEXT,
        link TEXT,
        notes TEXT,
        created_at TEXT,
        FOREIGN KEY(project_id) REFERENCES projects(id),
        FOREIGN KEY(owner_id) REFERENCES members(id)
    );
    CREATE TABLE IF NOT EXISTS email_logs (
        id TEXT PRIMARY KEY,
        subject TEXT NOT NULL,
        recipients TEXT,
        module TEXT,
        related_id TEXT,
        status TEXT DEFAULT 'queued',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS password_reset_tokens (
        token TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        expires_at TEXT,
        used_at TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS task_comments (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        user_id TEXT,
        user_name TEXT,
        comment TEXT NOT NULL,
        attachment_url TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS task_history (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        action TEXT,
        detail TEXT,
        user_name TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS document_revisions (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        revision TEXT NOT NULL,
        file_link TEXT,
        status TEXT DEFAULT 'Draft',
        issued_at TEXT,
        notes TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS document_comments (
        id TEXT PRIMARY KEY,
        document_id TEXT NOT NULL,
        source TEXT DEFAULT 'Internal',
        comment TEXT NOT NULL,
        response TEXT,
        owner_id TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'Open',
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS transmittals (
        id TEXT PRIMARY KEY,
        project_id TEXT,
        transmittal_no TEXT NOT NULL,
        direction TEXT DEFAULT 'Outgoing',
        recipients TEXT,
        purpose TEXT,
        document_ids TEXT,
        status TEXT DEFAULT 'Draft',
        sent_at TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS conversations (
        id TEXT PRIMARY KEY,
        conversation_name TEXT NOT NULL,
        conversation_type TEXT DEFAULT 'project',
        project_id TEXT,
        task_id TEXT,
        created_by TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS conversation_members (
        conversation_id TEXT,
        user_id TEXT,
        last_read_at TEXT,
        mute INTEGER DEFAULT 0,
        PRIMARY KEY(conversation_id, user_id)
    );
    CREATE TABLE IF NOT EXISTS messages (
        id TEXT PRIMARY KEY,
        conversation_id TEXT NOT NULL,
        sender_id TEXT,
        sender_name TEXT,
        message_content TEXT NOT NULL,
        message_type TEXT DEFAULT 'text',
        attachment_url TEXT,
        is_edited INTEGER DEFAULT 0,
        created_at TEXT,
        updated_at TEXT
    );
    CREATE TABLE IF NOT EXISTS rfqs (
        id TEXT PRIMARY KEY,
        bom_id TEXT,
        rfq_no TEXT NOT NULL,
        supplier TEXT,
        due_date TEXT,
        status TEXT DEFAULT 'Draft',
        notes TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS quotations (
        id TEXT PRIMARY KEY,
        rfq_id TEXT,
        supplier TEXT,
        amount REAL DEFAULT 0,
        currency TEXT DEFAULT 'VND',
        lead_time TEXT,
        status TEXT DEFAULT 'Received',
        file_link TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS delivery_tracking (
        id TEXT PRIMARY KEY,
        bom_item_id TEXT,
        po_no TEXT,
        supplier TEXT,
        ordered_date TEXT,
        promised_date TEXT,
        received_date TEXT,
        qty_ordered REAL DEFAULT 0,
        qty_received REAL DEFAULT 0,
        status TEXT DEFAULT 'Pending',
        notes TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS timesheets (
        id TEXT PRIMARY KEY,
        member_id TEXT,
        project_id TEXT,
        task_id TEXT,
        work_date TEXT,
        hours REAL DEFAULT 0,
        work_type TEXT DEFAULT 'Engineering',
        notes TEXT,
        created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    );
    """)
    try: c.execute("ALTER TABLE projects ADD COLUMN current_phase TEXT DEFAULT 'Budget Approval'")
    except: pass
    try: c.execute("ALTER TABLE projects ADD COLUMN phase_notes TEXT DEFAULT '{}'")
    except: pass
    for stmt in [
        "ALTER TABLE tasks ADD COLUMN phase_name TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN work_group_id TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN send_email INTEGER DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN email_status TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN start_date TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN reviewer_id TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN approver_id TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN watcher_ids TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN checklist TEXT DEFAULT '[]'",
        "ALTER TABLE tasks ADD COLUMN dependency_task_id TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN completed_at TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN parent_id TEXT DEFAULT ''",
        "ALTER TABLE tasks ADD COLUMN duration_days INTEGER DEFAULT 0",
        "ALTER TABLE tasks ADD COLUMN wbs_code TEXT DEFAULT ''",
    ]:
        try: c.execute(stmt)
        except: pass
    for stmt in [
        "ALTER TABLE work_groups ADD COLUMN parent_id TEXT DEFAULT ''",
        "ALTER TABLE work_groups ADD COLUMN duration_days INTEGER DEFAULT 0",
        "ALTER TABLE work_groups ADD COLUMN wbs_code TEXT DEFAULT ''",
        "ALTER TABLE project_phases ADD COLUMN parent_id TEXT DEFAULT ''",
        "ALTER TABLE project_phases ADD COLUMN duration_days INTEGER DEFAULT 0",
        "ALTER TABLE project_phases ADD COLUMN wbs_code TEXT DEFAULT ''",
        "ALTER TABLE project_phases ADD COLUMN owner_id TEXT DEFAULT ''",
    ]:
        try: c.execute(stmt)
        except: pass
    for stmt in [
        "ALTER TABLE inventory_items ADD COLUMN manufacturer TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN model_no TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN datasheet_link TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN standard_price REAL DEFAULT 0",
        "ALTER TABLE inventory_items ADD COLUMN currency TEXT DEFAULT 'VND'",
        "ALTER TABLE inventory_items ADD COLUMN supplier TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN lead_time TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN stock_qty REAL DEFAULT 0",
        "ALTER TABLE inventory_items ADD COLUMN alternative_model TEXT DEFAULT ''",
        "ALTER TABLE inventory_items ADD COLUMN status TEXT DEFAULT 'Active'",
    ]:
        try: c.execute(stmt)
        except: pass
    for stmt in [
        "ALTER TABLE documents ADD COLUMN owner_id TEXT DEFAULT ''",
        "ALTER TABLE documents ADD COLUMN planned_date TEXT DEFAULT ''",
        "ALTER TABLE documents ADD COLUMN actual_date TEXT DEFAULT ''",
        "ALTER TABLE documents ADD COLUMN document_code TEXT DEFAULT ''",
    ]:
        try: c.execute(stmt)
        except: pass
    try:
        c.execute("""UPDATE tasks
            SET phase_name=(SELECT current_phase FROM projects WHERE projects.id=tasks.project_id)
            WHERE COALESCE(phase_name,'')=''""")
    except: pass
    try:
        c.execute("""UPDATE tasks
            SET work_group_id=(
                SELECT wg.id FROM work_groups wg
                WHERE wg.project_id=tasks.project_id
                  AND wg.phase_name=tasks.phase_name
                ORDER BY wg.display_order, wg.created_at
                LIMIT 1
            )
            WHERE COALESCE(work_group_id,'')=''""")
    except: pass
    conn.commit()
    ensure_project_phases(conn)
    conn.commit(); conn.close()

def ensure_project_phases(conn):
    c = conn.cursor()
    projects = c.execute("SELECT id,current_phase,start_date,deadline,progress,leader_id FROM projects").fetchall()
    for project in projects:
        for idx, phase_name in enumerate(PHASES):
            exists = c.execute(
                "SELECT id FROM project_phases WHERE project_id=? AND phase_name=?",
                (project["id"], phase_name)
            ).fetchone()
            if exists:
                continue
            status = "Planned"
            progress = 0
            if phase_name == project["current_phase"]:
                status = "In Progress"
                progress = int(project["progress"] or 0)
            c.execute(
                """INSERT INTO project_phases
                   (id,project_id,phase_name,start_date,due_date,status,progress,display_order,notes,created_at,parent_id,duration_days,wbs_code,owner_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    str(uuid.uuid4())[:8],
                    project["id"],
                    phase_name,
                    project["start_date"] or "",
                    project["deadline"] or "",
                    status,
                    progress,
                    idx + 1,
                    "",
                    str(date.today()),
                    project["id"],
                    date_duration(project["start_date"], project["deadline"]),
                    f"PH-{idx+1:02d}",
                    project["leader_id"] or "",
                ),
            )

def seed_db():
    conn = get_db(); c = conn.cursor()
    # seed default admin user
    if c.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        today_str = str(date.today())
        admin_pwd = hash_password("admin123")
        users_seed = [
            ("u1","Team Leader","admin@autoteam.com","admin",admin_pwd,"0900000000","Management","Team Leader","Oil & Gas,PLC,SCADA","super_admin","active","#00d4aa",None,today_str),
            ("u2","Tran Van Hung","hung@autoteam.com","hung",hash_password("123456"),"0901111111","Automation","Project Manager","Siemens,PLC,P&ID","pm","active","#0099ff",None,today_str),
            ("u3","Nguyen Thi Mai","mai@autoteam.com","mai",hash_password("123456"),"0902222222","Automation","Lead Engineer","SCADA,HMI","lead","active","#a855f7",None,today_str),
            ("u4","Le Minh Tuan","tuan@autoteam.com","tuan",hash_password("123456"),"0903333333","Automation","Automation Engineer","PLC,Safety","engineer","active","#f59e0b",None,today_str),
            ("u5","Pham Quoc Bao","bao@autoteam.com","bao",hash_password("123456"),"0904444444","Document","Document Controller","MDR,Transmittal","doc_control","active","#22c55e",None,today_str),
            ("u6","Hoang Thi Lan","lan@autoteam.com","lan",hash_password("123456"),"0905555555","Procurement","Procurement","RFQ,Vendor","procurement","active","#ff6b35",None,today_str),
        ]
        c.executemany("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)", users_seed)

    if c.execute("SELECT COUNT(*) FROM app_update_logs WHERE version=?", (APP_VERSION,)).fetchone()[0] == 0:
        c.execute("INSERT INTO app_update_logs VALUES (?,?,?,?,?,?,?)",
            (
                str(uuid.uuid4())[:8],
                APP_VERSION,
                "Spec coverage MVP completed",
                "Added missing MVP screens and APIs from the functional spec: auth/profile, chat, document control, procurement, timesheet, backup, and richer task tracking.",
                json.dumps(["backend/main.py", "frontend/index.html", "data/autoteam.db"]),
                "Released",
                datetime.now().isoformat()
            ))


    # seed members/projects if empty
    if c.execute("SELECT COUNT(*) FROM members").fetchone()[0] == 0:
        today_str = str(date.today())
        members = [
            ("m1","Tran Van Hung","Team Leader","Siemens S7-300/400,SCADA WinCC,P&ID,Oil & Gas","hung@auto.com","10 nam kinh nghiem Oil & Gas",today_str),
            ("m2","Nguyen Thi Mai","SCADA Engineer","Ignition SCADA,Wonderware,HMI Design","mai@auto.com","Chuyen SCADA Power Plant",today_str),
            ("m3","Le Minh Tuan","PLC Programmer","Siemens S7-1500,Rockwell PLC,Safety PLC","tuan@auto.com","Chuyen PLC Safety",today_str),
            ("m4","Pham Quoc Bao","Instrumentation Engineer","HART,Foundation Fieldbus,Calibration","bao@auto.com","Instrumentation & Control",today_str),
            ("m5","Hoang Thi Lan","Automation Engineer","ABB DCS,DeltaV,SIL Assessment","lan@auto.com","DCS specialist",today_str),
            ("m6","Dang Van Phuc","Junior Engineer","AutoCAD,Wiring Design,PLC Basic","phuc@auto.com","Nhan vien moi",today_str),
        ]
        c.executemany("INSERT INTO members VALUES (?,?,?,?,?,?,?)", members)
        projects = [
            ("p1","PLC Upgrade - Wellhead WHP-A","Oil & Gas","PetroVietnam E&P","Nang cap PLC S7-300 len S7-1500","2026-01-15","2026-07-30","m1",65,"Dang trien khai","Construction",'{}',today_str),
            ("p2","SCADA Control Room - Power Plant 4","Power Plant","EVN Thu Duc","Xay dung SCADA trung tam 300MW","2026-02-01","2026-09-15","m2",35,"Dang trien khai","Engineering / Design",'{}',today_str),
            ("p3","Safety Shutdown System - Coal Mine","Mining","Vinacomin","Thiet ke SIS","2026-03-10","2026-12-31","m3",15,"Dang trien khai","Bidding / Tender",'{}',today_str),
            ("p4","DCS Commissioning - Gas Plant","Oil & Gas","PV Gas","Commissioning DCS ABB","2025-10-01","2026-06-01","m5",90,"Dang trien khai","Commissioning",'{}',today_str),
        ]
        c.executemany("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", projects)
        tasks = [
            ("t1","Lap trinh Function Block valve control","p1","m3","Viet FB cho 24 van","Cao","In Progress","2026-05-28",today_str,"Construction","wg2",0,""),
            ("t2","Thiet ke HMI overview platform","p1","m2","SCADA overview","Trung binh","Todo","2026-06-05",today_str,"Construction","wg2",0,""),
            ("t3","Review P&ID Rev.3","p1","m4","","Cao","Review",today_str,today_str,"Construction","wg1",0,""),
            ("t4","Cau hinh OPC-UA server","p2","m5","","Trung binh","In Progress","2026-06-10",today_str,"Engineering / Design","wg3",0,""),
            ("t5","Thiet ke wiring diagram MCC 6.6kV","p2","m6","AutoCAD","Thap","Todo","2026-06-20",today_str,"Engineering / Design","wg3",0,""),
            ("t7","Calibration 45 transmitter","p4","m4","","Trung binh","Done","2026-05-15",today_str,"Commissioning","wg5",0,""),
            ("t8","FAT DCS Cabinet","p4","m1","","Cao","Done","2026-05-10",today_str,"Commissioning","wg5",0,""),
        ]
        c.executemany("""INSERT INTO tasks
            (id,title,project_id,assignee_id,description,priority,status,due_date,created_at,
             phase_name,work_group_id,send_email,email_status)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""", tasks)
        docs = [
            ("d1","WHP-A PLC I/O List Rev.04","P&ID","p1","Danh sach I/O","04","Approved","","2026-05-18"),
            ("d2","SCADA Tag Database v2.3","SCADA","p2","Database tag","03","Review","","2026-05-20"),
            ("d3","SIS Logic Diagram","PLC Program","p3","Logic so do","01","Draft","","2026-05-22"),
            ("d4","DCS Wiring Drawing","Wiring","p4","Ban ve wiring","02","Approved","","2026-05-01"),
        ]
        c.executemany("""INSERT INTO documents
            (id,name,type,project_id,description,revision,status,link,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?)""", docs)

    # seed inventory if empty
    if c.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0] == 0:
        today_str = str(date.today())
        items = [
            ("i001","CAB-001","Cap dong 3x2.5mm2","Day cap & Phu kien","Cap dong boc PVC, chiu nhiet 70°C, 600V","m","IEC 60228",json.dumps(["cap","dong","PVC","600V"]),today_str,today_str),
            ("i002","CAB-002","Cap dong 3x4mm2","Day cap & Phu kien","Cap dong boc PVC 4mm2, 600V","m","IEC 60228",json.dumps(["cap","dong","PVC"]),today_str,today_str),
            ("i003","CAB-003","Cap dong 4x16mm2 XLPE","Day cap & Phu kien","Cap dong boc XLPE 4 loi, 1kV, chong chay","m","IEC 60502",json.dumps(["cap","XLPE","1kV","chong chay"]),today_str,today_str),
            ("i004","PLC-001","CPU Siemens S7-1500","PLC / I/O Module","CPU PLC S7-1516F-3 PN/DP Safety, 1MB Work memory","cai","CPU: S7-1516F",json.dumps(["PLC","Siemens","S7-1500","Safety"]),today_str,today_str),
            ("i005","PLC-002","Digital Input Module 32DI","PLC / I/O Module","Module DI 32 kenh 24VDC, 6ES7521","cai","32DI 24VDC",json.dumps(["PLC","DI","Siemens","module"]),today_str,today_str),
            ("i006","PLC-003","Digital Output Module 32DO","PLC / I/O Module","Module DO 32 kenh 24VDC/0.5A, 6ES7522","cai","32DO 24VDC",json.dumps(["PLC","DO","Siemens","module"]),today_str,today_str),
            ("i007","PLC-004","Analog Input Module 8AI","PLC / I/O Module","Module AI 8 kenh +/-10V, 4-20mA, 6ES7531","cai","8AI 4-20mA",json.dumps(["PLC","AI","Analog","Siemens"]),today_str,today_str),
            ("i008","HMI-001","Man hinh HMI 15 inch","HMI / SCADA Hardware","HMI cam ung 15 inch, 1280x800, IP65 front","cai","15in TFT Touch",json.dumps(["HMI","cam ung","IP65","SCADA"]),today_str,today_str),
            ("i009","INS-001","Pressure Transmitter 0-10 bar","Thiet bi do luong","Cam bien ap suat 4-20mA, HART, SS316, IP65","cai","4-20mA HART 0-10bar",json.dumps(["pressure","transmitter","HART","4-20mA"]),today_str,today_str),
            ("i010","INS-002","Temperature Transmitter PT100","Thiet bi do luong","Cam bien nhiet do PT100, 4-20mA, HART, IP65","cai","4-20mA HART PT100",json.dumps(["temperature","PT100","HART","4-20mA"]),today_str,today_str),
            ("i011","INS-003","Level Transmitter Ultrasonic","Thiet bi do luong","Cam bien muc sieu am, 4-20mA, IP67","cai","Ultrasonic 4-20mA",json.dumps(["level","ultrasonic","4-20mA"]),today_str,today_str),
            ("i012","CB-001","MCB 3P 32A","CB / MCB / MCCB / Relay","MCB 3 pha 32A, 6kA, 400V AC","cai","3P 32A 6kA",json.dumps(["MCB","CB","breaker","3P"]),today_str,today_str),
            ("i013","CB-002","MCCB 3P 250A","CB / MCB / MCCB / Relay","MCCB 3 pha 250A, 35kA, 690V, TM","cai","3P 250A 35kA",json.dumps(["MCCB","breaker","3P","250A"]),today_str,today_str),
            ("i014","CB-003","Relay trung gian 24VDC 8-pin","CB / MCB / MCCB / Relay","Relay trung gian 24VDC coil, 8 chan, 10A","cai","24VDC 10A 8-pin",json.dumps(["relay","trung gian","24VDC"]),today_str,today_str),
            ("i015","TRM-001","Terminal Block 4mm2 screw","Terminal Block / Cau dau","Cau dau day 4mm2 ren vit, 32A","cai","4mm2 32A screw",json.dumps(["terminal","cau dau","4mm2"]),today_str,today_str),
            ("i016","TRM-002","Terminal Block 10mm2 screw","Terminal Block / Cau dau","Cau dau day 10mm2 ren vit, 57A","cai","10mm2 57A screw",json.dumps(["terminal","cau dau","10mm2"]),today_str,today_str),
            ("i017","SWT-001","Contactor 3P 32A 24VDC","Switch / Contactor / VFD","Contactor 3P 32A, cuon day 24VDC, AC3","cai","3P 32A 24VDC coil",json.dumps(["contactor","3P","32A"]),today_str,today_str),
            ("i018","SWT-002","VFD bien tan 11kW 3P","Switch / Contactor / VFD","Bien tan 11kW, 380V 3 pha, IP20, RS485","cai","11kW 380V IP20",json.dumps(["VFD","bien tan","11kW","RS485"]),today_str,today_str),
            ("i019","SWT-003","Industrial Switch 8-port Managed","Switch / Contactor / VFD","Switch cong nghiep 8 port, managed, IP30, DIN rail","cai","8-port Managed IP30",json.dumps(["switch","managed","Ethernet","DIN rail"]),today_str,today_str),
            ("i020","CAP-001","Cable Tray 100x50mm Perforated","Phu kien cap","Mang cap duc lo 100x50mm, thep ma kem","m","100x50mm GI",json.dumps(["cable tray","mang cap","100x50"]),today_str,today_str),
            ("i021","CAP-002","Cable Gland M20 Stainless","Phu kien cap","Dau kep cap M20 inox SS316, IP68","cai","M20 SS316 IP68",json.dumps(["gland","M20","IP68","SS316"]),today_str,today_str),
            ("i022","PAN-001","Tu dien chu luc MDB IP54","Tu dien / Panel","Tu dien chu luc 800x600x300mm, IP54, son tinh dien","cai","800x600x300 IP54",json.dumps(["tu dien","MDB","IP54","panel"]),today_str,today_str),
            ("i023","UPS-001","Bo luu dien UPS 2kVA","May bien ap / UPS","UPS on-line 2kVA/1.8kW, 220VAC, thoi gian pin 30 phut","cai","2kVA 220VAC 30min",json.dumps(["UPS","luu dien","2kVA"]),today_str,today_str),
        ]
        c.executemany("""INSERT INTO inventory_items
            (id,item_code,name,category,description,unit,specs,tags,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?)""", items)

        vendors = [
            # Cable 3x2.5
            ("v001","i001","Cadivi","CVV-3x2.5","Viet Nam",25000,"VND","2-4 tuan","","Cap dong Viet Nam Cadivi",1,today_str),
            ("v002","i001","Taya","3x2.5 PVC","Dai Loan",28000,"VND","2-4 tuan","","",0,today_str),
            ("v003","i001","LS Cable","3x2.5mm2","Han Quoc",32000,"VND","4-6 tuan","","",0,today_str),
            # Cable 3x4
            ("v004","i002","Cadivi","CVV-3x4","Viet Nam",38000,"VND","2-4 tuan","","",1,today_str),
            ("v005","i002","LS Cable","3x4mm2","Han Quoc",45000,"VND","4-6 tuan","","",0,today_str),
            # Cable 4x16 XLPE
            ("v006","i003","Cadivi","CXV-4x16","Viet Nam",185000,"VND","2-4 tuan","","",1,today_str),
            ("v007","i003","Prysmian","4x16 XLPE","Italia",210000,"VND","6-8 tuan","","Premium brand",0,today_str),
            # CPU Siemens
            ("v008","i004","Siemens","6ES7516-3FN02-0AB0","Duc",85000000,"VND","8-12 tuan","https://siemens.com","CPU S7-1516F chinh hang",1,today_str),
            ("v009","i004","Siemens (qua PTE)","6ES7516-3FN02-0AB0","Duc",82000000,"VND","6-10 tuan","","Qua dai ly PTE",0,today_str),
            # DI Module
            ("v010","i005","Siemens","6ES7521-1BH10-0AA0","Duc",8500000,"VND","6-8 tuan","","DI 32ch chinh hang",1,today_str),
            ("v011","i005","Siemens (qua IQTECH)","6ES7521-1BH10-0AA0","Duc",8200000,"VND","4-6 tuan","","Qua IQTECH",0,today_str),
            # Pressure Transmitter
            ("v012","i009","Endress+Hauser","PMC71","Thuy Si",12000000,"VND","6-10 tuan","","E+H chinh hang",1,today_str),
            ("v013","i009","Yokogawa","EJX430A","Nhat Ban",11500000,"VND","8-12 tuan","","",0,today_str),
            ("v014","i009","Emerson","3051C","My",13000000,"VND","8-12 tuan","","Rosemount",0,today_str),
            ("v015","i009","Wika","S-10","Duc",5500000,"VND","4-6 tuan","","Gia re hon",0,today_str),
            # Temperature Transmitter
            ("v016","i010","Endress+Hauser","TMT82","Thuy Si",8500000,"VND","6-10 tuan","","",1,today_str),
            ("v017","i010","Yokogawa","YTA510","Nhat Ban",7800000,"VND","8-12 tuan","","",0,today_str),
            ("v018","i010","ABB","TTF300","Duc",9000000,"VND","8-12 tuan","","",0,today_str),
            # MCB
            ("v019","i012","Schneider","iC60N 3P 32A","Phap",850000,"VND","2-4 tuan","","Acti9 series",1,today_str),
            ("v020","i012","ABB","S203-C32","Duc",920000,"VND","2-4 tuan","","",0,today_str),
            ("v021","i012","LS","BKN 3P-32A","Han Quoc",620000,"VND","1-2 tuan","","Gia re",0,today_str),
            # MCCB
            ("v022","i013","Schneider","NSX250B TM250D","Phap",5800000,"VND","3-5 tuan","","",1,today_str),
            ("v023","i013","ABB","Tmax T4N 250","Duc",6200000,"VND","4-6 tuan","","",0,today_str),
            ("v024","i013","LS","ABS253b","Han Quoc",4200000,"VND","2-3 tuan","","",0,today_str),
            # Terminal
            ("v025","i015","Phoenix Contact","UK 4N","Duc",35000,"VND","3-5 tuan","","Phoenix chung hang",1,today_str),
            ("v026","i015","Weidmuller","WDU 4","Duc",32000,"VND","3-5 tuan","","",0,today_str),
            ("v027","i015","Chint","TB-45","Trung Quoc",8500,"VND","1-2 tuan","","Gia re",0,today_str),
            # Contactor
            ("v028","i017","Schneider","LC1D32BD","Phap",1250000,"VND","2-3 tuan","","TeSys D",1,today_str),
            ("v029","i017","Siemens","3RT2026","Duc",1380000,"VND","3-5 tuan","","",0,today_str),
            ("v030","i017","LS","MC-32a","Han Quoc",890000,"VND","1-2 tuan","","",0,today_str),
            # VFD
            ("v031","i018","ABB","ACS580-01-025A-4","Thuy Si",28500000,"VND","6-8 tuan","","ACS580 series",1,today_str),
            ("v032","i018","Siemens","SINAMICS G120","Duc",31000000,"VND","8-12 tuan","","",0,today_str),
            ("v033","i018","Schneider","ATV320U11N4B","Phap",26000000,"VND","4-6 tuan","","",0,today_str),
            # Managed Switch
            ("v034","i019","Moxa","EDS-408A","Dai Loan",8500000,"VND","4-6 tuan","","DIN rail managed",1,today_str),
            ("v035","i019","Hirschmann","RS20-0400T1T1SDAAE","Duc",12000000,"VND","6-8 tuan","","Premium",0,today_str),
            ("v036","i019","Cisco","IE-2000-8TC","My",15000000,"VND","6-10 tuan","","",0,today_str),
            # HMI
            ("v037","i008","Siemens","6AV2124-0QC02-0AX1","Duc",28000000,"VND","8-12 tuan","","KTP1500 Basic PN",1,today_str),
            ("v038","i008","Weintek","MT8150T","Dai Loan",12500000,"VND","3-5 tuan","","",0,today_str),
            ("v039","i008","Proface","GP4601T","Nhat Ban",18000000,"VND","6-8 tuan","","",0,today_str),
            # Cable Tray
            ("v040","i020","Legrand","337020","Phap",185000,"VND","2-3 tuan","","Cablofil",1,today_str),
            ("v041","i020","OBO Bettermann","MKS 100x50","Duc",195000,"VND","3-4 tuan","","",0,today_str),
            ("v042","i020","Local","100x50 GI","Viet Nam",85000,"VND","1 tuan","","San xuat trong nuoc",0,today_str),
            # UPS
            ("v043","i023","APC","SMT2200I","My",18500000,"VND","3-5 tuan","","Smart-UPS 2200VA",1,today_str),
            ("v044","i023","Eaton","5PX2200iRT","Irland",17800000,"VND","4-6 tuan","","",0,today_str),
            ("v045","i023","Emerson","Liebert GXT4","My",19500000,"VND","4-6 tuan","","",0,today_str),
        ]
        c.executemany("INSERT INTO inventory_vendors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", vendors)

    if c.execute("SELECT COUNT(*) FROM work_groups").fetchone()[0] == 0:
        today_str = str(date.today())
        groups = [
            ("wg1","p1","Construction","Cabinet Assembly","m1","2026-05-01","2026-06-15","In Progress",70,1,"Lap tu PLC, dau noi va kiem tra I/O",today_str),
            ("wg2","p1","Construction","Integration & Software","m3","2026-05-15","2026-07-10","In Progress",55,2,"Tich hop PLC S7-1500 va SCADA",today_str),
            ("wg3","p2","Engineering / Design","SCADA Design Package","m2","2026-04-01","2026-06-30","In Progress",40,1,"HMI overview, tag database, alarm list",today_str),
            ("wg4","p3","Bidding / Tender","Tender Technical Proposal","m3","2026-03-10","2026-06-05","In Progress",25,1,"Kiem tra input, BOM so bo va logic SIS",today_str),
            ("wg5","p4","Commissioning","FAT/SAT Punch List","m5","2026-05-01","2026-06-01","In Progress",90,1,"Dong punch list DCS truoc close-out",today_str),
        ]
        c.executemany("""INSERT INTO work_groups
            (id,project_id,phase_name,group_name,owner_id,start_date,due_date,status,progress,display_order,notes,created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""", groups)

    if c.execute("SELECT COUNT(*) FROM issues").fetchone()[0] == 0:
        today_str = str(date.today())
        issues = [
            ("is1","p1","Chua chot danh sach spare I/O","High","m1","Open","2026-05-30","Lam viec voi client de freeze IO List",today_str),
            ("is2","p2","Thieu input network topology","Medium","m2","Open","2026-06-03","Gui RFI cho khach hang",today_str),
            ("is3","p4","Punch list FAT con 3 diem","Low","m5","Monitoring","2026-05-28","Theo doi vendor update ban firmware",today_str),
        ]
        c.executemany("INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,?)", issues)

    if c.execute("SELECT COUNT(*) FROM notifications").fetchone()[0] == 0:
        now_str = datetime.now().isoformat()
        notifications = [
            ("n1","u1","Dashboard ready","AutoTeam PM da san sang voi du lieu demo theo spec MVP.","system","dashboard","",0,now_str),
            ("n2","u2","Task can theo doi","Co task deadline hom nay can review trong Kanban.","deadline","task","t3",0,now_str),
            ("n3","u6","BOM can cap nhat gia","BOM WHP-A Rev A co item thieu quotation/lead time.","bom","bom","bom1",0,now_str),
        ]
        c.executemany("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?)", notifications)

    if c.execute("SELECT COUNT(*) FROM bom_headers").fetchone()[0] == 0:
        today_str = str(date.today())
        boms = [
            ("bom1","p1","BOM-WHP-A-PLC","A","WHP-A PLC Upgrade Main BOM","For Review","VND",today_str),
            ("bom2","p2","BOM-SCADA-CR4","A","SCADA Control Room Hardware BOM","Draft","VND",today_str),
        ]
        c.executemany("INSERT INTO bom_headers VALUES (?,?,?,?,?,?,?,?)", boms)
        bom_items = [
            ("bi1","bom1","i004","10","CPU Siemens S7-1500 Safety",1,"cai",85000000,"VND","Siemens","8-12 tuan","Quoted","Main PLC CPU"),
            ("bi2","bom1","i005","20","Digital Input Module 32DI",4,"cai",8500000,"VND","Siemens","6-8 tuan","Need Check","Can confirm channel count"),
            ("bi3","bom1","i009","30","Pressure Transmitter 0-10 bar",8,"cai",12000000,"VND","Endress+Hauser","6-10 tuan","Quoted","Field device"),
            ("bi4","bom2","i008","10","Man hinh HMI 15 inch",2,"cai",0,"VND","","","Need Price","Waiting quotation"),
            ("bi5","bom2","i019","20","Industrial Switch 8-port Managed",3,"cai",0,"VND","","","Need Price","Need datasheet"),
        ]
        c.executemany("INSERT INTO bom_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", bom_items)

    if c.execute("SELECT COUNT(*) FROM eoffice_docs").fetchone()[0] == 0:
        today_str = str(date.today())
        eoffice_docs = [
            ("eo1","Incoming","PVEP-WHP-A-RFI-001","Client RFI - Spare I/O confirmation","p1","PVEP","Automation Team","m1","For Review","2026-05-30","","Can phan hoi truoc khi freeze BOM",today_str),
            ("eo2","Outgoing","ATPM-SCADA-TR-002","SCADA Tag Database Transmittal","p2","Automation Team","EVN Thu Duc","m2","Issued","2026-05-25","","Gui ban Rev.03 cho khach hang review",today_str),
            ("eo3","Incoming","PVG-DCS-COM-014","FAT punch list comment register","p4","PV Gas","Automation Team","m5","In Progress","2026-05-28","","Close comment truoc commissioning",today_str),
        ]
        c.executemany("INSERT INTO eoffice_docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", eoffice_docs)

    if c.execute("SELECT COUNT(*) FROM document_comments").fetchone()[0] == 0:
        today_str = str(date.today())
        doc_comments = [
            ("dc1","d2","Client","Confirm tag naming convention for alarm priority.","Revise alarm list and send response","m2","2026-05-30","Open",today_str),
            ("dc2","d1","Internal","Need IO spare percentage highlighted in MDR.","Updated in Rev.04","m1","2026-05-27","Closed",today_str),
        ]
        c.executemany("INSERT INTO document_comments VALUES (?,?,?,?,?,?,?,?,?)", doc_comments)

    if c.execute("SELECT COUNT(*) FROM document_revisions").fetchone()[0] == 0:
        today_str = str(date.today())
        revisions = [
            ("dr1","d1","04","","Approved","2026-05-18","Issued to client",today_str),
            ("dr2","d2","03","","Review","2026-05-20","Waiting client comment close",today_str),
        ]
        c.executemany("INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?,?)", revisions)

    if c.execute("SELECT COUNT(*) FROM transmittals").fetchone()[0] == 0:
        today_str = str(date.today())
        transmittals = [
            ("tr1","p2","ATPM-SCADA-TR-002","Outgoing","EVN Thu Duc","For Review","d2","Issued","2026-05-25",today_str),
        ]
        c.executemany("INSERT INTO transmittals VALUES (?,?,?,?,?,?,?,?,?,?)", transmittals)

    if c.execute("SELECT COUNT(*) FROM conversations").fetchone()[0] == 0:
        now_str = datetime.now().isoformat()
        conversations = [
            ("cv1","WHP-A Project Chat","project","p1","", "u1", now_str),
            ("cv2","Task Discussion - OPC UA","task","p2","t4", "u2", now_str),
        ]
        c.executemany("INSERT INTO conversations VALUES (?,?,?,?,?,?,?)", conversations)
        messages = [
            ("msg1","cv1","u1","Team Leader","Please close WHP-A spare IO comment before Friday.","text","",0,now_str,now_str),
            ("msg2","cv2","u2","Tran Van Hung","OPC-UA server config needs network topology input.","text","",0,now_str,now_str),
        ]
        c.executemany("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)", messages)

    if c.execute("SELECT COUNT(*) FROM rfqs").fetchone()[0] == 0:
        today_str = str(date.today())
        c.execute("INSERT INTO rfqs VALUES (?,?,?,?,?,?,?,?)",
            ("rfq1","bom1","RFQ-WHP-A-001","Siemens Vietnam","2026-06-02","Sent","CPU and IO modules",today_str))
        c.execute("INSERT INTO quotations VALUES (?,?,?,?,?,?,?,?,?)",
            ("qt1","rfq1","Siemens Vietnam",128000000,"VND","8-12 tuan","Received","",today_str))
        c.execute("INSERT INTO delivery_tracking VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            ("dl1","bi1","PO-WHP-A-001","Siemens Vietnam","2026-05-25","2026-07-15","",1,0,"Pending","Waiting factory confirmation",today_str))

    if c.execute("SELECT COUNT(*) FROM timesheets").fetchone()[0] == 0:
        today_str = str(date.today())
        timesheets = [
            ("ts1","m3","p1","t1",today_str,6,"PLC Programming","Function block implementation",today_str),
            ("ts2","m2","p2","t4",today_str,4,"SCADA","OPC-UA configuration",today_str),
        ]
        c.executemany("INSERT INTO timesheets VALUES (?,?,?,?,?,?,?,?,?)", timesheets)

    ensure_project_phases(conn)
    conn.commit(); conn.close()

# ─── MODELS ─────────────────────────────────────────────────
class MemberIn(BaseModel):
    name: str; role: Optional[str]=""; skills: Optional[str]=""; email: Optional[str]=""; notes: Optional[str]=""

class ProjectIn(BaseModel):
    name: str; type: Optional[str]="Oil & Gas"; client: Optional[str]=""; description: Optional[str]=""
    start_date: Optional[str]=""; deadline: Optional[str]=""; leader_id: Optional[str]=""
    progress: Optional[int]=0; status: Optional[str]="Cho bat dau"
    current_phase: Optional[str]="Budget Approval"; phase_notes: Optional[str]="{}"

class TaskIn(BaseModel):
    title: str; project_id: Optional[str]=""; assignee_id: Optional[str]=""; description: Optional[str]=""
    priority: Optional[str]="Trung binh"; status: Optional[str]="Todo"; due_date: Optional[str]=""
    phase_name: Optional[str]=""; work_group_id: Optional[str]=""
    send_email: Optional[bool]=False
    start_date: Optional[str]=""; reviewer_id: Optional[str]=""; approver_id: Optional[str]=""
    watcher_ids: Optional[str]=""; progress: Optional[int]=0; checklist: Optional[str]="[]"
    dependency_task_id: Optional[str]=""; completed_at: Optional[str]=""
    parent_id: Optional[str]=""; duration_days: Optional[int]=0; wbs_code: Optional[str]=""

class DocumentIn(BaseModel):
    name: str; type: Optional[str]="Khac"; project_id: Optional[str]=""; description: Optional[str]=""
    revision: Optional[str]="01"; status: Optional[str]="Draft"; link: Optional[str]=""
    owner_id: Optional[str]=""; planned_date: Optional[str]=""; actual_date: Optional[str]=""; document_code: Optional[str]=""

class PhaseUpdate(BaseModel):
    current_phase: str; phase_notes: Optional[str]="{}"

class ProjectPhaseIn(BaseModel):
    project_id: str
    phase_name: str
    start_date: Optional[str]=""
    due_date: Optional[str]=""
    status: Optional[str]="Planned"
    progress: Optional[int]=0
    display_order: Optional[int]=0
    notes: Optional[str]=""
    parent_id: Optional[str]=""
    duration_days: Optional[int]=0
    wbs_code: Optional[str]=""
    owner_id: Optional[str]=""

class InventoryItemIn(BaseModel):
    item_code: str; name: str; category: str; description: Optional[str]=""
    unit: Optional[str]="cai"; specs: Optional[str]=""; tags: Optional[str]="[]"
    manufacturer: Optional[str]=""; model_no: Optional[str]=""; datasheet_link: Optional[str]=""
    standard_price: Optional[float]=0; currency: Optional[str]="VND"; supplier: Optional[str]=""
    lead_time: Optional[str]=""; stock_qty: Optional[float]=0; alternative_model: Optional[str]=""
    status: Optional[str]="Active"

class VendorIn(BaseModel):
    item_id: str; brand: str; model_no: Optional[str]=""; origin: Optional[str]=""
    unit_price: Optional[float]=0; currency: Optional[str]="USD"
    lead_time: Optional[str]=""; datasheet_link: Optional[str]=""
    notes: Optional[str]=""; is_preferred: Optional[int]=0

class WorkGroupIn(BaseModel):
    project_id: str; phase_name: str; group_name: str
    owner_id: Optional[str]=""; start_date: Optional[str]=""; due_date: Optional[str]=""
    status: Optional[str]="Not Started"; progress: Optional[int]=0
    display_order: Optional[int]=0; notes: Optional[str]=""
    parent_id: Optional[str]=""; duration_days: Optional[int]=0; wbs_code: Optional[str]=""

class IssueIn(BaseModel):
    project_id: Optional[str]=""; title: str; severity: Optional[str]="Medium"
    owner_id: Optional[str]=""; status: Optional[str]="Open"; due_date: Optional[str]=""
    mitigation: Optional[str]=""

class NotificationIn(BaseModel):
    user_id: Optional[str]=""; title: str; message: Optional[str]=""
    notification_type: Optional[str]="system"; related_module: Optional[str]=""; related_id: Optional[str]=""

class BomIn(BaseModel):
    project_id: Optional[str]=""; bom_no: str; revision: Optional[str]="A"
    title: Optional[str]=""; status: Optional[str]="Draft"; currency: Optional[str]="VND"

class BomItemIn(BaseModel):
    bom_id: str; material_id: Optional[str]=""; item_no: Optional[str]=""
    description: Optional[str]=""; qty: Optional[float]=1; unit: Optional[str]="cai"
    unit_price: Optional[float]=0; currency: Optional[str]="VND"
    supplier: Optional[str]=""; lead_time: Optional[str]=""; status: Optional[str]="Need Check"; remark: Optional[str]=""

class EOfficeDocIn(BaseModel):
    direction: Optional[str]="Incoming"; doc_no: Optional[str]=""; title: str
    project_id: Optional[str]=""; sender: Optional[str]=""; receiver: Optional[str]=""
    owner_id: Optional[str]=""; status: Optional[str]="Draft"; due_date: Optional[str]=""
    link: Optional[str]=""; notes: Optional[str]=""

class EmailLogIn(BaseModel):
    subject: str; recipients: Optional[str]=""; module: Optional[str]=""
    related_id: Optional[str]=""; status: Optional[str]="queued"

class AuditLogIn(BaseModel):
    action: str
    module: Optional[str]="app"
    detail: Optional[str]=""

class TaskCommentIn(BaseModel):
    task_id: str; comment: str; attachment_url: Optional[str]=""

class DocumentRevisionIn(BaseModel):
    document_id: str; revision: str; file_link: Optional[str]=""
    status: Optional[str]="Draft"; issued_at: Optional[str]=""; notes: Optional[str]=""

class DocumentCommentIn(BaseModel):
    document_id: str; source: Optional[str]="Internal"; comment: str; response: Optional[str]=""
    owner_id: Optional[str]=""; due_date: Optional[str]=""; status: Optional[str]="Open"

class TransmittalIn(BaseModel):
    project_id: Optional[str]=""; transmittal_no: str; direction: Optional[str]="Outgoing"
    recipients: Optional[str]=""; purpose: Optional[str]=""; document_ids: Optional[str]=""
    status: Optional[str]="Draft"; sent_at: Optional[str]=""

class ConversationIn(BaseModel):
    conversation_name: str; conversation_type: Optional[str]="project"
    project_id: Optional[str]=""; task_id: Optional[str]=""; member_user_ids: Optional[str]=""

class MessageIn(BaseModel):
    conversation_id: str; message_content: str; message_type: Optional[str]="text"; attachment_url: Optional[str]=""

class RfqIn(BaseModel):
    bom_id: Optional[str]=""; rfq_no: str; supplier: Optional[str]=""
    due_date: Optional[str]=""; status: Optional[str]="Draft"; notes: Optional[str]=""

class QuotationIn(BaseModel):
    rfq_id: Optional[str]=""; supplier: Optional[str]=""; amount: Optional[float]=0
    currency: Optional[str]="VND"; lead_time: Optional[str]=""; status: Optional[str]="Received"
    file_link: Optional[str]=""

class DeliveryIn(BaseModel):
    bom_item_id: Optional[str]=""; po_no: Optional[str]=""; supplier: Optional[str]=""
    ordered_date: Optional[str]=""; promised_date: Optional[str]=""; received_date: Optional[str]=""
    qty_ordered: Optional[float]=0; qty_received: Optional[float]=0
    status: Optional[str]="Pending"; notes: Optional[str]=""

class TimesheetIn(BaseModel):
    member_id: Optional[str]=""; project_id: Optional[str]=""; task_id: Optional[str]=""
    work_date: Optional[str]=""; hours: Optional[float]=0; work_type: Optional[str]="Engineering"; notes: Optional[str]=""

# ─── INVENTORY ITEMS ────────────────────────────────────────
@app.get("/api/inventory/items")
def list_items(category: str="", search: str=""):
    conn = get_db()
    q = "SELECT * FROM inventory_items WHERE 1=1"
    params = []
    if category: q += " AND category=?"; params.append(category)
    if search:
        q += " AND (name LIKE ? OR item_code LIKE ? OR description LIKE ? OR tags LIKE ?)"
        params += [f"%{search}%"]*4
    q += " ORDER BY category, item_code"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/inventory/items/{item_id}")
def get_item(item_id: str):
    conn = get_db()
    item = conn.execute("SELECT * FROM inventory_items WHERE id=?", (item_id,)).fetchone()
    if not item: raise HTTPException(404, "Not found")
    vendors = conn.execute(
        "SELECT * FROM inventory_vendors WHERE item_id=? ORDER BY is_preferred DESC, brand",
        (item_id,)).fetchall()
    conn.close()
    return {"item": dict(item), "vendors": [dict(v) for v in vendors]}

@app.post("/api/inventory/items", status_code=201)
def create_item(item: InventoryItemIn):
    conn = get_db()
    iid = str(uuid.uuid4())[:8]
    now = str(date.today())
    conn.execute("""INSERT INTO inventory_items
        (id,item_code,name,category,description,unit,specs,tags,created_at,updated_at,
         manufacturer,model_no,datasheet_link,standard_price,currency,supplier,lead_time,
         stock_qty,alternative_model,status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (iid, item.item_code, item.name, item.category, item.description,
         item.unit, item.specs, item.tags, now, now, item.manufacturer, item.model_no,
         item.datasheet_link, item.standard_price, item.currency, item.supplier,
         item.lead_time, item.stock_qty, item.alternative_model, item.status))
    conn.commit(); conn.close()
    return {"id": iid}

@app.put("/api/inventory/items/{item_id}")
def update_item(item_id: str, item: InventoryItemIn):
    conn = get_db()
    conn.execute("""UPDATE inventory_items SET item_code=?,name=?,category=?,description=?,
        unit=?,specs=?,tags=?,updated_at=?,manufacturer=?,model_no=?,datasheet_link=?,
        standard_price=?,currency=?,supplier=?,lead_time=?,stock_qty=?,alternative_model=?,
        status=? WHERE id=?""",
        (item.item_code, item.name, item.category, item.description,
         item.unit, item.specs, item.tags, str(date.today()), item.manufacturer,
         item.model_no, item.datasheet_link, item.standard_price, item.currency,
         item.supplier, item.lead_time, item.stock_qty, item.alternative_model,
         item.status, item_id))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/inventory/items/{item_id}")
def delete_item(item_id: str):
    conn = get_db()
    conn.execute("DELETE FROM inventory_vendors WHERE item_id=?", (item_id,))
    conn.execute("DELETE FROM inventory_items WHERE id=?", (item_id,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── INVENTORY VENDORS ──────────────────────────────────────
@app.get("/api/inventory/vendors/{item_id}")
def list_vendors(item_id: str):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM inventory_vendors WHERE item_id=? ORDER BY is_preferred DESC, brand",
        (item_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/inventory/vendors", status_code=201)
def create_vendor(v: VendorIn):
    conn = get_db()
    vid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO inventory_vendors VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (vid, v.item_id, v.brand, v.model_no, v.origin, v.unit_price,
         v.currency, v.lead_time, v.datasheet_link, v.notes, v.is_preferred, str(date.today())))
    conn.commit(); conn.close()
    return {"id": vid}

@app.put("/api/inventory/vendors/{vid}")
def update_vendor(vid: str, v: VendorIn):
    conn = get_db()
    conn.execute("""UPDATE inventory_vendors SET brand=?,model_no=?,origin=?,unit_price=?,
        currency=?,lead_time=?,datasheet_link=?,notes=?,is_preferred=? WHERE id=?""",
        (v.brand, v.model_no, v.origin, v.unit_price, v.currency,
         v.lead_time, v.datasheet_link, v.notes, v.is_preferred, vid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/inventory/vendors/{vid}")
def delete_vendor(vid: str):
    conn = get_db()
    conn.execute("DELETE FROM inventory_vendors WHERE id=?", (vid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/api/inventory/categories")
def get_categories():
    return ITEM_CATEGORIES

@app.get("/api/inventory/stats")
def inventory_stats():
    conn = get_db(); c = conn.cursor()
    total_items = c.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0]
    total_vendors = c.execute("SELECT COUNT(*) FROM inventory_vendors").fetchone()[0]
    by_cat = c.execute(
        "SELECT category, COUNT(*) as cnt FROM inventory_items GROUP BY category ORDER BY cnt DESC"
    ).fetchall()
    conn.close()
    return {"total_items": total_items, "total_vendors": total_vendors,
            "by_category": [dict(r) for r in by_cat]}

# ─── EXISTING ENDPOINTS ─────────────────────────────────────
@app.get("/api/members")
def list_members():
    conn=get_db(); rows=conn.execute("SELECT * FROM members ORDER BY created_at").fetchall(); conn.close(); return [dict(r) for r in rows]

@app.post("/api/members",status_code=201)
def create_member(m:MemberIn):
    conn=get_db(); mid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO members VALUES (?,?,?,?,?,?,?)",(mid,m.name,m.role,m.skills,m.email,m.notes,str(date.today())))
    conn.commit();conn.close();return{"id":mid}

@app.put("/api/members/{mid}")
def update_member(mid:str,m:MemberIn):
    conn=get_db(); conn.execute("UPDATE members SET name=?,role=?,skills=?,email=?,notes=? WHERE id=?",(m.name,m.role,m.skills,m.email,m.notes,mid)); conn.commit();conn.close();return{"ok":True}

@app.delete("/api/members/{mid}")
def delete_member(mid:str):
    conn=get_db();conn.execute("DELETE FROM members WHERE id=?",(mid,));conn.commit();conn.close();return{"ok":True}

@app.get("/api/projects")
def list_projects():
    conn=get_db();rows=conn.execute("SELECT p.*,m.name as leader_name FROM projects p LEFT JOIN members m ON p.leader_id=m.id ORDER BY p.created_at DESC").fetchall();conn.close();return[dict(r) for r in rows]

@app.post("/api/projects",status_code=201)
def create_project(p:ProjectIn):
    conn=get_db();pid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO projects VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(pid,p.name,p.type,p.client,p.description,p.start_date,p.deadline,p.leader_id,p.progress,p.status,p.current_phase,p.phase_notes,str(date.today())))
    conn.commit();conn.close();return{"id":pid}

@app.put("/api/projects/{pid}")
def update_project(pid:str,p:ProjectIn):
    conn=get_db();conn.execute("UPDATE projects SET name=?,type=?,client=?,description=?,start_date=?,deadline=?,leader_id=?,progress=?,status=?,current_phase=?,phase_notes=? WHERE id=?",(p.name,p.type,p.client,p.description,p.start_date,p.deadline,p.leader_id,p.progress,p.status,p.current_phase,p.phase_notes,pid));conn.commit();conn.close();return{"ok":True}

@app.delete("/api/projects/{pid}")
def delete_project(pid:str):
    conn=get_db();conn.execute("DELETE FROM projects WHERE id=?",(pid,));conn.commit();conn.close();return{"ok":True}

@app.put("/api/projects/{pid}/phase")
def update_phase(pid:str,body:PhaseUpdate):
    conn=get_db();conn.execute("UPDATE projects SET current_phase=?,phase_notes=? WHERE id=?",(body.current_phase,body.phase_notes,pid));conn.commit();conn.close();return{"ok":True}

@app.get("/api/project-phases")
def list_project_phases(project_id: str=""):
    conn=get_db()
    ensure_project_phases(conn)
    conn.commit()
    q="""SELECT ph.*, p.name AS project_name, p.type AS project_type, p.client AS client,
                m.name AS owner_name
         FROM project_phases ph
         LEFT JOIN projects p ON ph.project_id=p.id
         LEFT JOIN members m ON ph.owner_id=m.id
         WHERE 1=1"""
    params=[]
    if project_id:
        q += " AND ph.project_id=?"; params.append(project_id)
    q += " ORDER BY p.created_at DESC, ph.display_order, ph.created_at"
    rows=conn.execute(q,params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/project-phases",status_code=201)
def create_project_phase(body:ProjectPhaseIn):
    conn=get_db(); pid=str(uuid.uuid4())[:8]
    display_order = body.display_order or (
        conn.execute("SELECT COALESCE(MAX(display_order),0)+1 FROM project_phases WHERE project_id=?",
                     (body.project_id,)).fetchone()[0]
    )
    conn.execute("""INSERT INTO project_phases
        (id,project_id,phase_name,start_date,due_date,status,progress,display_order,notes,created_at,parent_id,duration_days,wbs_code,owner_id)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (pid,body.project_id,body.phase_name,body.start_date,body.due_date,body.status,
         body.progress,display_order,body.notes,str(date.today()),body.parent_id or body.project_id,
         body.duration_days or date_duration(body.start_date, body.due_date),body.wbs_code,body.owner_id))
    conn.commit(); conn.close()
    return {"id":pid}

@app.put("/api/project-phases/{phase_id}")
def update_project_phase(phase_id:str,body:ProjectPhaseIn):
    conn=get_db()
    old=conn.execute("SELECT * FROM project_phases WHERE id=?",(phase_id,)).fetchone()
    if not old:
        conn.close(); raise HTTPException(404,"Phase not found")
    conn.execute("""UPDATE project_phases SET project_id=?,phase_name=?,start_date=?,due_date=?,
        status=?,progress=?,display_order=?,notes=?,parent_id=?,duration_days=?,wbs_code=?,owner_id=? WHERE id=?""",
        (body.project_id,body.phase_name,body.start_date,body.due_date,body.status,
         body.progress,body.display_order,body.notes,body.parent_id or body.project_id,
         body.duration_days or date_duration(body.start_date, body.due_date),body.wbs_code,body.owner_id,phase_id))
    if old["phase_name"] != body.phase_name or old["project_id"] != body.project_id:
        conn.execute("UPDATE work_groups SET project_id=?,phase_name=? WHERE project_id=? AND phase_name=?",
            (body.project_id,body.phase_name,old["project_id"],old["phase_name"]))
        conn.execute("UPDATE tasks SET project_id=?,phase_name=? WHERE project_id=? AND phase_name=?",
            (body.project_id,body.phase_name,old["project_id"],old["phase_name"]))
        conn.execute("UPDATE projects SET current_phase=? WHERE id=? AND current_phase=?",
            (body.phase_name,body.project_id,old["phase_name"]))
    conn.commit(); conn.close()
    return {"ok":True}

@app.delete("/api/project-phases/{phase_id}")
def delete_project_phase(phase_id:str):
    conn=get_db()
    ph=conn.execute("SELECT * FROM project_phases WHERE id=?",(phase_id,)).fetchone()
    if not ph:
        conn.close(); raise HTTPException(404,"Phase not found")
    groups=conn.execute("SELECT id FROM work_groups WHERE project_id=? AND phase_name=?",
        (ph["project_id"],ph["phase_name"])).fetchall()
    group_ids=[g["id"] for g in groups]
    if group_ids:
        placeholders=",".join(["?"]*len(group_ids))
        conn.execute(f"DELETE FROM tasks WHERE project_id=? AND (phase_name=? OR work_group_id IN ({placeholders}))",
            [ph["project_id"],ph["phase_name"],*group_ids])
    else:
        conn.execute("DELETE FROM tasks WHERE project_id=? AND phase_name=?",
            (ph["project_id"],ph["phase_name"]))
    conn.execute("DELETE FROM work_groups WHERE project_id=? AND phase_name=?",
        (ph["project_id"],ph["phase_name"]))
    conn.execute("DELETE FROM project_phases WHERE id=?",(phase_id,))
    next_phase=conn.execute("""SELECT phase_name FROM project_phases
        WHERE project_id=? ORDER BY display_order, created_at LIMIT 1""",(ph["project_id"],)).fetchone()
    if next_phase:
        conn.execute("UPDATE projects SET current_phase=? WHERE id=? AND current_phase=?",
            (next_phase["phase_name"],ph["project_id"],ph["phase_name"]))
    conn.commit(); conn.close()
    return {"ok":True}

@app.get("/api/tasks")
def list_tasks():
    conn=get_db();rows=conn.execute("""SELECT t.*,m.name as assignee_name,p.name as project_name,
        wg.group_name as work_group_name, rv.name as reviewer_name, ap.name as approver_name,
        dep.title as dependency_task_title
        FROM tasks t
        LEFT JOIN members m ON t.assignee_id=m.id
        LEFT JOIN projects p ON t.project_id=p.id
        LEFT JOIN work_groups wg ON t.work_group_id=wg.id
        LEFT JOIN members rv ON t.reviewer_id=rv.id
        LEFT JOIN members ap ON t.approver_id=ap.id
        LEFT JOIN tasks dep ON t.dependency_task_id=dep.id
        ORDER BY t.created_at DESC""").fetchall();conn.close();return[dict(r) for r in rows]

@app.post("/api/tasks",status_code=201)
def create_task(t:TaskIn):
    conn=get_db();tid=str(uuid.uuid4())[:8]
    email_status = "queued" if t.send_email else ""
    conn.execute("""INSERT INTO tasks
        (id,title,project_id,assignee_id,description,priority,status,due_date,created_at,
         phase_name,work_group_id,send_email,email_status,start_date,reviewer_id,approver_id,
         watcher_ids,progress,checklist,dependency_task_id,completed_at,parent_id,duration_days,wbs_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (tid,t.title,t.project_id,t.assignee_id,t.description,t.priority,t.status,t.due_date,
         str(date.today()),t.phase_name,t.work_group_id,1 if t.send_email else 0,email_status,
         t.start_date,t.reviewer_id,t.approver_id,t.watcher_ids,t.progress,t.checklist,
         t.dependency_task_id,t.completed_at,t.parent_id or t.work_group_id or t.phase_name or t.project_id,
         t.duration_days or date_duration(t.start_date, t.due_date),t.wbs_code))
    conn.execute("INSERT INTO task_history VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4())[:8], tid, "create", f"Tạo task: {t.title}", "System", datetime.now().isoformat()))
    if t.send_email:
        assignee = conn.execute("SELECT name,email FROM members WHERE id=?", (t.assignee_id,)).fetchone()
        project = conn.execute("SELECT name FROM projects WHERE id=?", (t.project_id,)).fetchone()
        recipient = assignee["email"] if assignee else ""
        conn.execute("INSERT INTO email_logs VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], f"Task Assigned: {t.title}", recipient,
             "task", tid, "queued", datetime.now().isoformat()))
        conn.execute("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], "", "Task assigned",
             f"{t.title} - {project['name'] if project else ''}", "task", "task", tid, 0,
             datetime.now().isoformat()))
    conn.commit();conn.close();return{"id":tid}

@app.put("/api/tasks/{tid}")
def update_task(tid:str,t:TaskIn):
    conn=get_db();email_status = "queued" if t.send_email else ""
    conn.execute("""UPDATE tasks SET title=?,project_id=?,assignee_id=?,description=?,
        priority=?,status=?,due_date=?,phase_name=?,work_group_id=?,send_email=?,
        start_date=?,reviewer_id=?,approver_id=?,watcher_ids=?,progress=?,checklist=?,
        dependency_task_id=?,completed_at=?,parent_id=?,duration_days=?,wbs_code=?,
        email_status=CASE WHEN ?=1 AND COALESCE(email_status,'')='' THEN 'queued' ELSE email_status END
        WHERE id=?""",
        (t.title,t.project_id,t.assignee_id,t.description,t.priority,t.status,t.due_date,
         t.phase_name,t.work_group_id,1 if t.send_email else 0,t.start_date,t.reviewer_id,
         t.approver_id,t.watcher_ids,t.progress,t.checklist,t.dependency_task_id,t.completed_at,
         t.parent_id or t.work_group_id or t.phase_name or t.project_id,
         t.duration_days or date_duration(t.start_date, t.due_date),t.wbs_code,
         1 if t.send_email else 0,tid))
    conn.execute("INSERT INTO task_history VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4())[:8], tid, "update", f"Cập nhật task: {t.title} / {t.status}", "System", datetime.now().isoformat()))
    if t.send_email:
        assignee = conn.execute("SELECT name,email FROM members WHERE id=?", (t.assignee_id,)).fetchone()
        recipient = assignee["email"] if assignee else ""
        conn.execute("INSERT INTO email_logs VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], f"Task Assigned/Updated: {t.title}", recipient,
             "task", tid, "queued", datetime.now().isoformat()))
    conn.commit();conn.close();return{"ok":True}

@app.delete("/api/tasks/{tid}")
def delete_task(tid:str):
    conn=get_db();conn.execute("DELETE FROM tasks WHERE id=?",(tid,));conn.commit();conn.close();return{"ok":True}

@app.get("/api/task-comments")
def list_task_comments(task_id: str=""):
    conn=get_db()
    q="SELECT * FROM task_comments WHERE 1=1"; params=[]
    if task_id:
        q += " AND task_id=?"; params.append(task_id)
    q += " ORDER BY created_at DESC LIMIT 300"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/task-comments", status_code=201)
def create_task_comment(body: TaskCommentIn):
    conn=get_db(); cid=str(uuid.uuid4())[:8]; now=datetime.now().isoformat()
    conn.execute("INSERT INTO task_comments VALUES (?,?,?,?,?,?,?)",
        (cid, body.task_id, "", "System", body.comment, body.attachment_url, now))
    conn.execute("INSERT INTO task_history VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4())[:8], body.task_id, "comment", body.comment[:160], "System", now))
    conn.commit(); conn.close()
    return {"id": cid}

@app.get("/api/task-history")
def list_task_history(task_id: str=""):
    conn=get_db()
    q="SELECT * FROM task_history WHERE 1=1"; params=[]
    if task_id:
        q += " AND task_id=?"; params.append(task_id)
    q += " ORDER BY created_at DESC LIMIT 300"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.get("/api/documents")
def list_documents():
    conn=get_db();rows=conn.execute("""SELECT d.*,p.name as project_name,m.name as owner_name
        FROM documents d
        LEFT JOIN projects p ON d.project_id=p.id
        LEFT JOIN members m ON d.owner_id=m.id
        ORDER BY d.updated_at DESC""").fetchall();conn.close();return[dict(r) for r in rows]

@app.post("/api/documents",status_code=201)
def create_document(d:DocumentIn):
    conn=get_db();did=str(uuid.uuid4())[:8]
    conn.execute("""INSERT INTO documents
        (id,name,type,project_id,description,revision,status,link,updated_at,
         owner_id,planned_date,actual_date,document_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (did,d.name,d.type,d.project_id,d.description,d.revision,d.status,d.link,str(date.today()),
         d.owner_id,d.planned_date,d.actual_date,d.document_code))
    conn.execute("INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?,?)",
        (str(uuid.uuid4())[:8],did,d.revision,d.link,d.status,d.actual_date,"Initial revision",datetime.now().isoformat()))
    conn.commit();conn.close();return{"id":did}

@app.put("/api/documents/{did}")
def update_document(did:str,d:DocumentIn):
    conn=get_db();conn.execute("""UPDATE documents SET name=?,type=?,project_id=?,description=?,
        revision=?,status=?,link=?,updated_at=?,owner_id=?,planned_date=?,actual_date=?,
        document_code=? WHERE id=?""",
        (d.name,d.type,d.project_id,d.description,d.revision,d.status,d.link,str(date.today()),
         d.owner_id,d.planned_date,d.actual_date,d.document_code,did));conn.commit();conn.close();return{"ok":True}

@app.delete("/api/documents/{did}")
def delete_document(did:str):
    conn=get_db();conn.execute("DELETE FROM documents WHERE id=?",(did,));conn.commit();conn.close();return{"ok":True}

@app.get("/api/document-revisions")
def list_document_revisions(document_id: str=""):
    conn=get_db()
    q="SELECT * FROM document_revisions WHERE 1=1"; params=[]
    if document_id:
        q += " AND document_id=?"; params.append(document_id)
    q += " ORDER BY created_at DESC"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/document-revisions", status_code=201)
def create_document_revision(body: DocumentRevisionIn):
    conn=get_db(); rid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO document_revisions VALUES (?,?,?,?,?,?,?,?)",
        (rid, body.document_id, body.revision, body.file_link, body.status,
         body.issued_at, body.notes, datetime.now().isoformat()))
    conn.execute("UPDATE documents SET revision=?,status=?,link=?,actual_date=?,updated_at=? WHERE id=?",
        (body.revision, body.status, body.file_link, body.issued_at, str(date.today()), body.document_id))
    conn.commit(); conn.close()
    return {"id": rid}

@app.get("/api/document-comments")
def list_document_comments(document_id: str="", status: str=""):
    conn=get_db()
    q="""SELECT dc.*, d.name AS document_name, m.name AS owner_name
         FROM document_comments dc
         LEFT JOIN documents d ON dc.document_id=d.id
         LEFT JOIN members m ON dc.owner_id=m.id
         WHERE 1=1"""
    params=[]
    if document_id:
        q += " AND dc.document_id=?"; params.append(document_id)
    if status:
        q += " AND dc.status=?"; params.append(status)
    q += " ORDER BY dc.created_at DESC"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/document-comments", status_code=201)
def create_document_comment(body: DocumentCommentIn):
    conn=get_db(); cid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO document_comments VALUES (?,?,?,?,?,?,?,?,?)",
        (cid, body.document_id, body.source, body.comment, body.response,
         body.owner_id, body.due_date, body.status, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": cid}

@app.put("/api/document-comments/{cid}")
def update_document_comment(cid: str, body: DocumentCommentIn):
    conn=get_db()
    conn.execute("""UPDATE document_comments SET document_id=?,source=?,comment=?,response=?,
        owner_id=?,due_date=?,status=? WHERE id=?""",
        (body.document_id, body.source, body.comment, body.response,
         body.owner_id, body.due_date, body.status, cid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/api/transmittals")
def list_transmittals(project_id: str=""):
    conn=get_db()
    q="""SELECT tr.*, p.name AS project_name FROM transmittals tr
         LEFT JOIN projects p ON tr.project_id=p.id WHERE 1=1"""
    params=[]
    if project_id:
        q += " AND tr.project_id=?"; params.append(project_id)
    q += " ORDER BY tr.created_at DESC"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/transmittals", status_code=201)
def create_transmittal(body: TransmittalIn):
    conn=get_db(); tid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO transmittals VALUES (?,?,?,?,?,?,?,?,?,?)",
        (tid, body.project_id, body.transmittal_no, body.direction, body.recipients,
         body.purpose, body.document_ids, body.status, body.sent_at, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": tid}

@app.get("/api/stats")
def get_stats():
    conn=get_db();c=conn.cursor()
    inv=c.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0]
    overdue=c.execute("SELECT COUNT(*) FROM tasks WHERE due_date<? AND status!='Done'",(str(date.today()),)).fetchone()[0]
    result={"projects":c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
           "tasks_done":c.execute("SELECT COUNT(*) FROM tasks WHERE status='Done'").fetchone()[0],
           "tasks_open":c.execute("SELECT COUNT(*) FROM tasks WHERE status!='Done'").fetchone()[0],
           "members":c.execute("SELECT COUNT(*) FROM members").fetchone()[0],
           "tasks_today":c.execute("SELECT COUNT(*) FROM tasks WHERE due_date=? AND status!='Done'",(str(date.today()),)).fetchone()[0],
           "tasks_overdue":overdue,
           "inventory_items":inv,
           "boms":c.execute("SELECT COUNT(*) FROM bom_headers").fetchone()[0],
           "issues_open":c.execute("SELECT COUNT(*) FROM issues WHERE status!='Closed'").fetchone()[0],
           "documents":c.execute("SELECT COUNT(*) FROM documents").fetchone()[0],
           "eoffice":c.execute("SELECT COUNT(*) FROM eoffice_docs").fetchone()[0],
           "notifications_unread":c.execute("SELECT COUNT(*) FROM notifications WHERE is_read=0").fetchone()[0]}
    conn.close()
    return result

@app.get("/api/phases")
def get_phases(): return PHASES

def rows_to_dicts(rows):
    return [dict(r) for r in rows]

def load_people_for_email_sync(conn):
    people = []
    users = conn.execute("""
        SELECT id, full_name AS name, email, department, position, role, 'user' AS source
        FROM users
        WHERE COALESCE(email,'')!='' AND COALESCE(status,'active')='active'
        ORDER BY full_name
    """).fetchall()
    members = conn.execute("""
        SELECT id, name, email, '' AS department, role AS position, role, 'member' AS source
        FROM members
        WHERE COALESCE(email,'')!=''
        ORDER BY name
    """).fetchall()
    for row in list(users) + list(members):
        people.append(dict(row))
    return people

def ensure_recent_email_demo(conn, limit=10):
    subjects = [
        "Client document review request",
        "Task assignment follow up",
        "RFQ clarification from supplier",
        "MDR revision approval",
        "Meeting minutes for project team",
        "Procurement delivery update",
        "Site query response",
        "Timesheet reminder",
        "E-Office incoming document",
        "Weekly project status",
    ]
    modules = ["eoffice", "task", "procurement", "document", "project"]
    statuses = ["received", "read", "queued", "sent"]
    now = datetime.now()
    for person in load_people_for_email_sync(conn):
        email = (person.get("email") or "").strip()
        if not email:
            continue
        existing = conn.execute(
            "SELECT COUNT(*) FROM email_logs WHERE lower(COALESCE(recipients,'')) LIKE ?",
            (f"%{email.lower()}%",)
        ).fetchone()[0]
        slot = 1
        while existing < limit and slot <= limit:
            mail_id = f"eomail_{person['source']}_{person['id']}_{slot}"
            created_at = (now - timedelta(hours=slot * 6)).isoformat()
            conn.execute(
                "INSERT OR IGNORE INTO email_logs VALUES (?,?,?,?,?,?,?)",
                (
                    mail_id,
                    f"{subjects[(slot - 1) % len(subjects)]} - {person['name']}",
                    email,
                    modules[(slot - 1) % len(modules)],
                    person["id"],
                    statuses[(slot - 1) % len(statuses)],
                    created_at,
                ),
            )
            existing = conn.execute(
                "SELECT COUNT(*) FROM email_logs WHERE lower(COALESCE(recipients,'')) LIKE ?",
                (f"%{email.lower()}%",)
            ).fetchone()[0]
            slot += 1

def latest_emails_by_person(conn, limit=10):
    limit = max(1, min(int(limit or 10), 10))
    ensure_recent_email_demo(conn, limit)
    conn.commit()
    logs = rows_to_dicts(conn.execute(
        "SELECT * FROM email_logs ORDER BY datetime(created_at) DESC, created_at DESC"
    ).fetchall())
    payload = []
    for person in load_people_for_email_sync(conn):
        email = (person.get("email") or "").strip()
        email_l = email.lower()
        person_logs = [
            log for log in logs
            if email_l and email_l in str(log.get("recipients") or "").lower()
        ][:limit]
        payload.append({
            "person_id": person["id"],
            "person_name": person["name"],
            "person_type": person["source"],
            "email": email,
            "department": person.get("department") or "",
            "position": person.get("position") or person.get("role") or "",
            "emails": person_logs,
            "email_count": len(person_logs),
        })
    return payload

@app.get("/api/app-info")
def app_info():
    return {
        "name": "AutoTeam PM",
        "version": APP_VERSION,
        "release_date": APP_RELEASE_DATE,
        "build_label": APP_BUILD_LABEL,
        "changelog": APP_CHANGELOG,
    }

@app.get("/api/app-updates")
def list_app_updates(limit: int = 20):
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM app_update_logs ORDER BY created_at DESC LIMIT ?",
        (max(1, min(limit, 100)),)
    ).fetchall()
    conn.close()
    return rows_to_dicts(rows)

# ─── WORK GROUPS / PHASE DETAIL ─────────────────────────────
@app.get("/api/work-groups")
def list_work_groups(project_id: str="", phase_name: str=""):
    conn = get_db()
    q = """SELECT wg.*, p.name AS project_name, m.name AS owner_name
           FROM work_groups wg
           LEFT JOIN projects p ON wg.project_id=p.id
           LEFT JOIN members m ON wg.owner_id=m.id
           WHERE 1=1"""
    params = []
    if project_id:
        q += " AND wg.project_id=?"; params.append(project_id)
    if phase_name:
        q += " AND wg.phase_name=?"; params.append(phase_name)
    q += " ORDER BY wg.project_id, wg.phase_name, wg.display_order, wg.created_at"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/work-groups", status_code=201)
def create_work_group(body: WorkGroupIn):
    conn = get_db(); wid = str(uuid.uuid4())[:8]
    conn.execute("""INSERT INTO work_groups
        (id,project_id,phase_name,group_name,owner_id,start_date,due_date,status,progress,display_order,notes,created_at,parent_id,duration_days,wbs_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (wid, body.project_id, body.phase_name, body.group_name, body.owner_id,
         body.start_date, body.due_date, body.status, body.progress,
         body.display_order, body.notes, str(date.today()), body.parent_id or body.phase_name,
         body.duration_days or date_duration(body.start_date, body.due_date), body.wbs_code))
    conn.commit(); conn.close()
    return {"id": wid}

@app.put("/api/work-groups/{wid}")
def update_work_group(wid: str, body: WorkGroupIn):
    conn = get_db()
    conn.execute("""UPDATE work_groups SET project_id=?,phase_name=?,group_name=?,
        owner_id=?,start_date=?,due_date=?,status=?,progress=?,display_order=?,notes=?,
        parent_id=?,duration_days=?,wbs_code=?
        WHERE id=?""",
        (body.project_id, body.phase_name, body.group_name, body.owner_id,
         body.start_date, body.due_date, body.status, body.progress,
         body.display_order, body.notes, body.parent_id or body.phase_name,
         body.duration_days or date_duration(body.start_date, body.due_date), body.wbs_code, wid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/work-groups/{wid}")
def delete_work_group(wid: str):
    conn = get_db()
    conn.execute("UPDATE tasks SET work_group_id='' WHERE work_group_id=?", (wid,))
    conn.execute("DELETE FROM work_groups WHERE id=?", (wid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── ISSUES / RISKS ─────────────────────────────────────────
@app.get("/api/issues")
def list_issues(project_id: str="", status: str=""):
    conn = get_db()
    q = """SELECT i.*, p.name AS project_name, m.name AS owner_name
           FROM issues i
           LEFT JOIN projects p ON i.project_id=p.id
           LEFT JOIN members m ON i.owner_id=m.id
           WHERE 1=1"""
    params = []
    if project_id:
        q += " AND i.project_id=?"; params.append(project_id)
    if status:
        q += " AND i.status=?"; params.append(status)
    q += " ORDER BY CASE i.severity WHEN 'Critical' THEN 1 WHEN 'High' THEN 2 WHEN 'Medium' THEN 3 ELSE 4 END, i.due_date"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/issues", status_code=201)
def create_issue(body: IssueIn):
    conn = get_db(); iid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO issues VALUES (?,?,?,?,?,?,?,?,?)",
        (iid, body.project_id, body.title, body.severity, body.owner_id,
         body.status, body.due_date, body.mitigation, str(date.today())))
    conn.commit(); conn.close()
    return {"id": iid}

@app.put("/api/issues/{iid}")
def update_issue(iid: str, body: IssueIn):
    conn = get_db()
    conn.execute("""UPDATE issues SET project_id=?,title=?,severity=?,owner_id=?,
        status=?,due_date=?,mitigation=? WHERE id=?""",
        (body.project_id, body.title, body.severity, body.owner_id,
         body.status, body.due_date, body.mitigation, iid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/issues/{iid}")
def delete_issue(iid: str):
    conn = get_db()
    conn.execute("DELETE FROM issues WHERE id=?", (iid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── NOTIFICATIONS ──────────────────────────────────────────
@app.get("/api/notifications")
def list_notifications(user_id: str="", unread_only: int=0):
    conn = get_db()
    q = "SELECT * FROM notifications WHERE 1=1"
    params = []
    if user_id:
        q += " AND (user_id=? OR user_id='')"; params.append(user_id)
    if unread_only:
        q += " AND is_read=0"
    q += " ORDER BY created_at DESC LIMIT 100"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/notifications", status_code=201)
def create_notification(body: NotificationIn):
    conn = get_db(); nid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO notifications VALUES (?,?,?,?,?,?,?,?,?)",
        (nid, body.user_id, body.title, body.message, body.notification_type,
         body.related_module, body.related_id, 0, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": nid}

@app.put("/api/notifications/{nid}/read")
def mark_notification_read(nid: str):
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1 WHERE id=?", (nid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/notifications/read-all")
def mark_all_notifications_read():
    conn = get_db()
    conn.execute("UPDATE notifications SET is_read=1")
    conn.commit(); conn.close()
    return {"ok": True}

# ─── BOM / PROCUREMENT ──────────────────────────────────────
@app.get("/api/conversations")
def list_conversations():
    conn = get_db()
    rows = conn.execute("""SELECT c.*, p.name AS project_name, t.title AS task_title,
        (SELECT message_content FROM messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message,
        (SELECT created_at FROM messages m WHERE m.conversation_id=c.id ORDER BY m.created_at DESC LIMIT 1) AS last_message_at
        FROM conversations c
        LEFT JOIN projects p ON c.project_id=p.id
        LEFT JOIN tasks t ON c.task_id=t.id
        ORDER BY COALESCE(last_message_at,c.created_at) DESC""").fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/conversations", status_code=201)
def create_conversation(body: ConversationIn):
    conn = get_db(); cid = str(uuid.uuid4())[:8]; now = datetime.now().isoformat()
    conn.execute("INSERT INTO conversations VALUES (?,?,?,?,?,?,?)",
        (cid, body.conversation_name, body.conversation_type, body.project_id,
         body.task_id, "", now))
    for uid in [x.strip() for x in (body.member_user_ids or "").split(",") if x.strip()]:
        conn.execute("INSERT OR IGNORE INTO conversation_members VALUES (?,?,?,?)", (cid, uid, "", 0))
    conn.commit(); conn.close()
    return {"id": cid}

@app.get("/api/conversations/{cid}/messages")
def list_messages(cid: str):
    conn = get_db()
    rows = conn.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at", (cid,)).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/messages", status_code=201)
def create_message(body: MessageIn):
    conn = get_db(); mid = str(uuid.uuid4())[:8]; now = datetime.now().isoformat()
    conn.execute("INSERT INTO messages VALUES (?,?,?,?,?,?,?,?,?,?)",
        (mid, body.conversation_id, "", "System", body.message_content, body.message_type,
         body.attachment_url, 0, now, now))
    conn.commit(); conn.close()
    return {"id": mid}

@app.get("/api/boms")
def list_boms(project_id: str=""):
    conn = get_db()
    q = """SELECT b.*, p.name AS project_name,
           COALESCE(SUM(bi.qty * bi.unit_price), 0) AS total_cost,
           COUNT(bi.id) AS item_count
           FROM bom_headers b
           LEFT JOIN projects p ON b.project_id=p.id
           LEFT JOIN bom_items bi ON b.id=bi.bom_id
           WHERE 1=1"""
    params = []
    if project_id:
        q += " AND b.project_id=?"; params.append(project_id)
    q += " GROUP BY b.id ORDER BY b.created_at DESC"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.get("/api/boms/{bid}")
def get_bom(bid: str):
    conn = get_db()
    bom = conn.execute("""SELECT b.*, p.name AS project_name FROM bom_headers b
        LEFT JOIN projects p ON b.project_id=p.id WHERE b.id=?""", (bid,)).fetchone()
    if not bom:
        conn.close()
        raise HTTPException(404, "BOM not found")
    items = conn.execute("""SELECT bi.*, ii.item_code, ii.name AS material_name, ii.category
        FROM bom_items bi
        LEFT JOIN inventory_items ii ON bi.material_id=ii.id
        WHERE bi.bom_id=?
        ORDER BY CAST(bi.item_no AS INTEGER), bi.item_no""", (bid,)).fetchall()
    conn.close()
    return {"bom": dict(bom), "items": rows_to_dicts(items)}

@app.post("/api/boms", status_code=201)
def create_bom(body: BomIn):
    conn = get_db(); bid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO bom_headers VALUES (?,?,?,?,?,?,?,?)",
        (bid, body.project_id, body.bom_no, body.revision, body.title,
         body.status, body.currency, str(date.today())))
    conn.commit(); conn.close()
    return {"id": bid}

@app.put("/api/boms/{bid}")
def update_bom(bid: str, body: BomIn):
    conn = get_db()
    conn.execute("""UPDATE bom_headers SET project_id=?,bom_no=?,revision=?,title=?,
        status=?,currency=? WHERE id=?""",
        (body.project_id, body.bom_no, body.revision, body.title,
         body.status, body.currency, bid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/boms/{bid}")
def delete_bom(bid: str):
    conn = get_db()
    conn.execute("DELETE FROM bom_items WHERE bom_id=?", (bid,))
    conn.execute("DELETE FROM bom_headers WHERE id=?", (bid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/bom-items", status_code=201)
def create_bom_item(body: BomItemIn):
    conn = get_db(); iid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO bom_items VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (iid, body.bom_id, body.material_id, body.item_no, body.description,
         body.qty, body.unit, body.unit_price, body.currency, body.supplier,
         body.lead_time, body.status, body.remark))
    conn.commit(); conn.close()
    return {"id": iid}

@app.put("/api/bom-items/{iid}")
def update_bom_item(iid: str, body: BomItemIn):
    conn = get_db()
    conn.execute("""UPDATE bom_items SET bom_id=?,material_id=?,item_no=?,description=?,
        qty=?,unit=?,unit_price=?,currency=?,supplier=?,lead_time=?,status=?,remark=?
        WHERE id=?""",
        (body.bom_id, body.material_id, body.item_no, body.description,
         body.qty, body.unit, body.unit_price, body.currency, body.supplier,
         body.lead_time, body.status, body.remark, iid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/bom-items/{iid}")
def delete_bom_item(iid: str):
    conn = get_db()
    conn.execute("DELETE FROM bom_items WHERE id=?", (iid,))
    conn.commit(); conn.close()
    return {"ok": True}

# ─── E-OFFICE / DOCUMENT WORKFLOW ───────────────────────────
@app.get("/api/rfqs")
def list_rfqs(bom_id: str=""):
    conn = get_db()
    q="""SELECT r.*, b.bom_no, b.title AS bom_title FROM rfqs r
         LEFT JOIN bom_headers b ON r.bom_id=b.id WHERE 1=1"""
    params=[]
    if bom_id:
        q += " AND r.bom_id=?"; params.append(bom_id)
    q += " ORDER BY r.created_at DESC"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/rfqs", status_code=201)
def create_rfq(body: RfqIn):
    conn = get_db(); rid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO rfqs VALUES (?,?,?,?,?,?,?,?)",
        (rid, body.bom_id, body.rfq_no, body.supplier, body.due_date,
         body.status, body.notes, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": rid}

@app.get("/api/quotations")
def list_quotations(rfq_id: str=""):
    conn = get_db()
    q="""SELECT q.*, r.rfq_no FROM quotations q
         LEFT JOIN rfqs r ON q.rfq_id=r.id WHERE 1=1"""
    params=[]
    if rfq_id:
        q += " AND q.rfq_id=?"; params.append(rfq_id)
    q += " ORDER BY q.created_at DESC"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/quotations", status_code=201)
def create_quotation(body: QuotationIn):
    conn = get_db(); qid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO quotations VALUES (?,?,?,?,?,?,?,?,?)",
        (qid, body.rfq_id, body.supplier, body.amount, body.currency,
         body.lead_time, body.status, body.file_link, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": qid}

@app.get("/api/deliveries")
def list_deliveries():
    conn = get_db()
    rows = conn.execute("""SELECT d.*, bi.item_no, bi.description AS bom_item_description,
        bh.bom_no FROM delivery_tracking d
        LEFT JOIN bom_items bi ON d.bom_item_id=bi.id
        LEFT JOIN bom_headers bh ON bi.bom_id=bh.id
        ORDER BY d.created_at DESC""").fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/deliveries", status_code=201)
def create_delivery(body: DeliveryIn):
    conn = get_db(); did=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO delivery_tracking VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (did, body.bom_item_id, body.po_no, body.supplier, body.ordered_date,
         body.promised_date, body.received_date, body.qty_ordered, body.qty_received,
         body.status, body.notes, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": did}

@app.get("/api/eoffice")
def list_eoffice(direction: str="", project_id: str=""):
    conn = get_db()
    q = """SELECT e.*, p.name AS project_name, m.name AS owner_name
           FROM eoffice_docs e
           LEFT JOIN projects p ON e.project_id=p.id
           LEFT JOIN members m ON e.owner_id=m.id
           WHERE 1=1"""
    params = []
    if direction:
        q += " AND e.direction=?"; params.append(direction)
    if project_id:
        q += " AND e.project_id=?"; params.append(project_id)
    q += " ORDER BY e.created_at DESC, e.due_date"
    rows = conn.execute(q, params).fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.get("/api/eoffice/latest-emails")
def list_eoffice_latest_emails(limit: int = 10):
    conn = get_db()
    payload = latest_emails_by_person(conn, limit)
    conn.close()
    return payload

@app.post("/api/eoffice", status_code=201)
def create_eoffice(body: EOfficeDocIn):
    conn = get_db(); eid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO eoffice_docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (eid, body.direction, body.doc_no, body.title, body.project_id,
         body.sender, body.receiver, body.owner_id, body.status,
         body.due_date, body.link, body.notes, str(date.today())))
    conn.commit(); conn.close()
    return {"id": eid}

@app.put("/api/eoffice/{eid}")
def update_eoffice(eid: str, body: EOfficeDocIn):
    conn = get_db()
    conn.execute("""UPDATE eoffice_docs SET direction=?,doc_no=?,title=?,project_id=?,
        sender=?,receiver=?,owner_id=?,status=?,due_date=?,link=?,notes=? WHERE id=?""",
        (body.direction, body.doc_no, body.title, body.project_id,
         body.sender, body.receiver, body.owner_id, body.status,
         body.due_date, body.link, body.notes, eid))
    conn.commit(); conn.close()
    return {"ok": True}

@app.delete("/api/eoffice/{eid}")
def delete_eoffice(eid: str):
    conn = get_db()
    conn.execute("DELETE FROM eoffice_docs WHERE id=?", (eid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/api/email-logs")
def list_email_logs():
    conn = get_db()
    rows = conn.execute("SELECT * FROM email_logs ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return rows_to_dicts(rows)

@app.post("/api/email-logs", status_code=201)
def create_email_log(body: EmailLogIn):
    conn = get_db(); eid = str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO email_logs VALUES (?,?,?,?,?,?,?)",
        (eid, body.subject, body.recipients, body.module,
         body.related_id, body.status, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": eid}

@app.get("/api/timesheets")
def list_timesheets(member_id: str="", project_id: str=""):
    conn = get_db()
    q="""SELECT ts.*, m.name AS member_name, p.name AS project_name, t.title AS task_title
         FROM timesheets ts
         LEFT JOIN members m ON ts.member_id=m.id
         LEFT JOIN projects p ON ts.project_id=p.id
         LEFT JOIN tasks t ON ts.task_id=t.id
         WHERE 1=1"""
    params=[]
    if member_id:
        q += " AND ts.member_id=?"; params.append(member_id)
    if project_id:
        q += " AND ts.project_id=?"; params.append(project_id)
    q += " ORDER BY ts.work_date DESC, ts.created_at DESC LIMIT 300"
    rows=conn.execute(q, params).fetchall(); conn.close()
    return rows_to_dicts(rows)

@app.post("/api/timesheets", status_code=201)
def create_timesheet(body: TimesheetIn):
    conn = get_db(); tid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO timesheets VALUES (?,?,?,?,?,?,?,?,?)",
        (tid, body.member_id, body.project_id, body.task_id, body.work_date or str(date.today()),
         body.hours, body.work_type, body.notes, datetime.now().isoformat()))
    conn.commit(); conn.close()
    return {"id": tid}

@app.get("/api/reports/summary")
def reports_summary():
    conn = get_db(); c = conn.cursor()
    data = {
        "tasks_by_status": rows_to_dicts(c.execute(
            "SELECT status, COUNT(*) AS cnt FROM tasks GROUP BY status ORDER BY cnt DESC").fetchall()),
        "tasks_by_priority": rows_to_dicts(c.execute(
            "SELECT priority, COUNT(*) AS cnt FROM tasks GROUP BY priority ORDER BY cnt DESC").fetchall()),
        "projects_by_phase": rows_to_dicts(c.execute(
            "SELECT current_phase AS phase, COUNT(*) AS cnt FROM projects GROUP BY current_phase").fetchall()),
        "documents_by_status": rows_to_dicts(c.execute(
            "SELECT status, COUNT(*) AS cnt FROM documents GROUP BY status").fetchall()),
        "workload": rows_to_dicts(c.execute("""SELECT m.id, m.name,
            SUM(CASE WHEN t.status!='Done' THEN 1 ELSE 0 END) AS open_tasks,
            SUM(CASE WHEN t.status='Done' THEN 1 ELSE 0 END) AS done_tasks
            FROM members m LEFT JOIN tasks t ON m.id=t.assignee_id
            GROUP BY m.id, m.name ORDER BY open_tasks DESC""").fetchall()),
        "bom_costs": rows_to_dicts(c.execute("""SELECT b.id, b.bom_no, b.title,
            COALESCE(SUM(bi.qty * bi.unit_price), 0) AS total_cost, b.currency
            FROM bom_headers b LEFT JOIN bom_items bi ON b.id=bi.bom_id
            GROUP BY b.id ORDER BY total_cost DESC""").fetchall()),
        "material_gaps": rows_to_dicts(c.execute("""SELECT id, item_code, name, category
            FROM inventory_items
            WHERE COALESCE(specs,'')='' OR COALESCE(tags,'')='' OR COALESCE(standard_price,0)=0
            LIMIT 25""").fetchall()),
        "document_comments_open": rows_to_dicts(c.execute("""SELECT dc.*, d.name AS document_name
            FROM document_comments dc LEFT JOIN documents d ON dc.document_id=d.id
            WHERE dc.status!='Closed' ORDER BY dc.due_date LIMIT 25""").fetchall()),
        "procurement_pending": rows_to_dicts(c.execute("""SELECT * FROM delivery_tracking
            WHERE status NOT IN ('Received','Closed') ORDER BY promised_date LIMIT 25""").fetchall()),
        "timesheet_by_member": rows_to_dicts(c.execute("""SELECT m.name, COALESCE(SUM(ts.hours),0) AS hours
            FROM members m LEFT JOIN timesheets ts ON m.id=ts.member_id
            GROUP BY m.id, m.name ORDER BY hours DESC""").fetchall()),
    }
    conn.close()
    return data

@app.get("/api/search")
def global_search(q: str=""):
    term = f"%{q}%"
    conn = get_db()
    result = {"projects": [], "tasks": [], "documents": [], "materials": []}
    if q:
        result["projects"] = rows_to_dicts(conn.execute(
            "SELECT id,name,type,client,status FROM projects WHERE name LIKE ? OR client LIKE ? LIMIT 10",
            (term, term)).fetchall())
        result["tasks"] = rows_to_dicts(conn.execute(
            "SELECT id,title,status,priority,due_date FROM tasks WHERE title LIKE ? OR description LIKE ? LIMIT 10",
            (term, term)).fetchall())
        result["documents"] = rows_to_dicts(conn.execute(
            "SELECT id,name,type,status,revision FROM documents WHERE name LIKE ? OR description LIKE ? LIMIT 10",
            (term, term)).fetchall())
        result["materials"] = rows_to_dicts(conn.execute(
            "SELECT id,item_code,name,category FROM inventory_items WHERE item_code LIKE ? OR name LIKE ? OR description LIKE ? LIMIT 10",
            (term, term, term)).fetchall())
    conn.close()
    return result


# ═══════════════════════════════════════════════════════════
# RBAC / AUTHENTICATION ENDPOINTS
# ═══════════════════════════════════════════════════════════
from fastapi import Header, Depends, Request

class RegisterIn(BaseModel):
    full_name: str
    email: str
    username: Optional[str] = ""
    password: str
    phone: Optional[str] = ""
    department: Optional[str] = ""
    position: Optional[str] = ""
    skills: Optional[str] = ""

class LoginIn(BaseModel):
    email: str
    password: str

class UserUpdateIn(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = ""
    department: Optional[str] = ""
    position: Optional[str] = ""
    skills: Optional[str] = ""
    role: str
    status: str

class PasswordChangeIn(BaseModel):
    old_password: str
    new_password: str

class ProfileUpdateIn(BaseModel):
    full_name: str
    phone: Optional[str] = ""
    department: Optional[str] = ""
    position: Optional[str] = ""
    skills: Optional[str] = ""

class ForgotPasswordIn(BaseModel):
    email: str

class ResetPasswordIn(BaseModel):
    token: str
    new_password: str

def get_current_user(authorization: str = Header(None)):
    """Lấy user hiện tại từ token. Trả None nếu chưa đăng nhập."""
    if not authorization:
        return None
    token = authorization.replace("Bearer ", "").strip()
    conn = get_db()
    row = conn.execute(
        "SELECT u.*, s.expires_at FROM sessions s JOIN users u ON s.user_id=u.id WHERE s.token=?",
        (token,)).fetchone()
    if row and row["expires_at"]:
        try:
            if datetime.fromisoformat(row["expires_at"]) < datetime.now():
                conn.execute("DELETE FROM sessions WHERE token=?", (token,))
                conn.commit(); conn.close()
                return None
        except Exception:
            pass
    conn.close()
    return dict(row) if row else None

def require_auth(authorization: str = Header(None)):
    user = get_current_user(authorization)
    if not user:
        raise HTTPException(401, "Chưa đăng nhập hoặc phiên hết hạn")
    if user["status"] != "active":
        raise HTTPException(403, "Tài khoản chưa được kích hoạt")
    return user

def log_audit(user, action, module, detail=""):
    try:
        conn = get_db()
        conn.execute("INSERT INTO audit_logs VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], user.get("id") if user else None,
             user.get("full_name") if user else "System",
             action, module, detail, datetime.now().isoformat()))
        conn.commit(); conn.close()
    except: pass

@app.middleware("http")
async def api_auth_guard(request: Request, call_next):
    path = request.url.path
    public = (
        "/api/app-info", "/api/auth/login", "/api/auth/register",
        "/api/auth/forgot-password", "/api/auth/reset-password"
    )
    if request.method == "OPTIONS" or not path.startswith("/api/") or path in public:
        return await call_next(request)
    user = get_current_user(request.headers.get("authorization"))
    if not user:
        return JSONResponse({"detail": "Chưa đăng nhập hoặc phiên hết hạn"}, status_code=401)
    if user.get("status") != "active":
        return JSONResponse({"detail": "Tài khoản chưa được kích hoạt"}, status_code=403)
    return await call_next(request)

@app.get("/api/auth/roles")
def get_roles():
    return {"roles": ROLES, "permissions": PERMISSION_MATRIX}

@app.post("/api/auth/register", status_code=201)
def register(body: RegisterIn):
    conn = get_db()
    exists = conn.execute("SELECT id FROM users WHERE email=?", (body.email,)).fetchone()
    if exists:
        conn.close()
        raise HTTPException(400, "Email đã được đăng ký")
    uid = str(uuid.uuid4())[:8]
    colors = ["#00d4aa","#0099ff","#a855f7","#f59e0b","#22c55e","#ff6b35","#06b6d4","#f43f5e"]
    color = colors[hash(uid) % len(colors)]
    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (uid, body.full_name, body.email, body.username or body.email,
         hash_password(body.password), body.phone, body.department,
         body.position, body.skills, "engineer", "pending", color, None, str(date.today())))
    conn.commit(); conn.close()
    return {"id": uid, "message": "Đăng ký thành công. Chờ Admin duyệt tài khoản."}

@app.post("/api/auth/forgot-password")
def forgot_password(body: ForgotPasswordIn):
    conn = get_db()
    user = conn.execute("SELECT id,email FROM users WHERE email=? OR username=?", (body.email, body.email)).fetchone()
    if user:
        token = make_token()
        expires_at = (datetime.now() + timedelta(hours=2)).isoformat()
        conn.execute("INSERT INTO password_reset_tokens VALUES (?,?,?,?,?)",
            (token, user["id"], expires_at, "", datetime.now().isoformat()))
        conn.execute("INSERT INTO email_logs VALUES (?,?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], "Password reset token", user["email"],
             "auth", user["id"], "queued", datetime.now().isoformat()))
        conn.commit(); conn.close()
        return {"ok": True, "message": "Reset token đã được ghi vào Email Log demo.", "reset_token": token}
    conn.close()
    return {"ok": True, "message": "Nếu email tồn tại, hệ thống sẽ gửi hướng dẫn reset."}

@app.post("/api/auth/reset-password")
def reset_password(body: ResetPasswordIn):
    conn = get_db()
    row = conn.execute("SELECT * FROM password_reset_tokens WHERE token=? AND COALESCE(used_at,'')=''",
        (body.token,)).fetchone()
    if not row:
        conn.close()
        raise HTTPException(400, "Reset token không hợp lệ")
    if row["expires_at"] and datetime.fromisoformat(row["expires_at"]) < datetime.now():
        conn.close()
        raise HTTPException(400, "Reset token đã hết hạn")
    conn.execute("UPDATE users SET password_hash=? WHERE id=?", (hash_password(body.new_password), row["user_id"]))
    conn.execute("UPDATE password_reset_tokens SET used_at=? WHERE token=?", (datetime.now().isoformat(), body.token))
    conn.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
    conn.commit(); conn.close()
    return {"ok": True}

@app.post("/api/auth/login")
def login(body: LoginIn):
    conn = get_db()
    cutoff = (datetime.now() - timedelta(minutes=15)).isoformat()
    failed_count = conn.execute(
        "SELECT COUNT(*) FROM login_history WHERE email=? AND status='failed' AND created_at>?",
        (body.email, cutoff)).fetchone()[0]
    if failed_count >= MAX_FAILED_LOGIN:
        conn.close()
        raise HTTPException(429, "Tài khoản bị khóa tạm thời 15 phút do đăng nhập sai nhiều lần")
    row = conn.execute("SELECT * FROM users WHERE email=? OR username=?",
                       (body.email, body.email)).fetchone()
    if not row or not verify_password(body.password, row["password_hash"]):
        conn.execute("INSERT INTO login_history VALUES (?,?,?,?,?,?)",
            (str(uuid.uuid4())[:8], None, body.email, "", "failed", datetime.now().isoformat()))
        conn.commit(); conn.close()
        log_audit({"id": None, "full_name": "Anonymous"}, "login_failed", "auth", body.email)
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")
    user = dict(row)
    if user["status"] == "pending":
        conn.close()
        raise HTTPException(403, "Tài khoản đang chờ duyệt")
    if user["status"] in ("suspended", "disabled", "rejected"):
        conn.close()
        raise HTTPException(403, "Tài khoản đã bị khóa")
    token = make_token()
    expires_at = (datetime.now() + timedelta(minutes=SESSION_TIMEOUT_MINUTES)).isoformat()
    conn.execute("INSERT INTO sessions VALUES (?,?,?,?)",
        (token, user["id"], datetime.now().isoformat(), expires_at))
    conn.execute("UPDATE users SET last_login_at=? WHERE id=?",
        (datetime.now().isoformat(), user["id"]))
    conn.execute("INSERT INTO login_history VALUES (?,?,?,?,?,?)",
        (str(uuid.uuid4())[:8], user["id"], user["email"], "", "success", datetime.now().isoformat()))
    conn.commit(); conn.close()
    log_audit(user, "login", "auth", user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"], "full_name": user["full_name"], "email": user["email"],
            "role": user["role"], "role_name": ROLES.get(user["role"], {}).get("name", user["role"]),
            "department": user["department"], "position": user["position"],
            "phone": user["phone"], "skills": user["skills"],
            "avatar_color": user["avatar_color"],
            "permissions": PERMISSION_MATRIX.get(user["role"], {}),
        }
    }

@app.post("/api/auth/logout")
def logout(authorization: str = Header(None)):
    user = get_current_user(authorization) if authorization else None
    if authorization:
        token = authorization.replace("Bearer ", "").strip()
        conn = get_db()
        conn.execute("DELETE FROM sessions WHERE token=?", (token,))
        conn.commit(); conn.close()
    if user:
        log_audit(user, "logout", "auth", user.get("email", ""))
    return {"ok": True}

@app.get("/api/auth/me")
def get_me(user: dict = Depends(require_auth)):
    return {
        "id": user["id"], "full_name": user["full_name"], "email": user["email"],
        "role": user["role"], "role_name": ROLES.get(user["role"], {}).get("name", user["role"]),
        "department": user["department"], "position": user["position"],
        "phone": user["phone"], "skills": user["skills"],
        "avatar_color": user["avatar_color"],
        "permissions": PERMISSION_MATRIX.get(user["role"], {}),
    }

@app.put("/api/auth/me")
def update_me(body: ProfileUpdateIn, user: dict = Depends(require_auth)):
    conn = get_db()
    conn.execute("""UPDATE users SET full_name=?,phone=?,department=?,position=?,skills=?
        WHERE id=?""", (body.full_name, body.phone, body.department, body.position, body.skills, user["id"]))
    conn.commit(); conn.close()
    log_audit(user, "update_profile", "auth", body.full_name)
    return {"ok": True}

@app.post("/api/auth/change-password")
def change_password(body: PasswordChangeIn, user: dict = Depends(require_auth)):
    if not verify_password(body.old_password, user["password_hash"]):
        raise HTTPException(400, "Mật khẩu cũ không đúng")
    conn = get_db()
    conn.execute("UPDATE users SET password_hash=? WHERE id=?",
        (hash_password(body.new_password), user["id"]))
    conn.commit(); conn.close()
    log_audit(user, "change_password", "auth", "User changed own password")
    return {"ok": True}

# ─── USER MANAGEMENT (Admin) ───
@app.get("/api/users")
def list_users(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("SELECT id,full_name,email,username,phone,department,position,skills,role,status,avatar_color,last_login_at,created_at FROM users ORDER BY created_at DESC").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["role_name"] = ROLES.get(d["role"], {}).get("name", d["role"])
        out.append(d)
    return out

@app.put("/api/users/{uid}")
def update_user(uid: str, body: UserUpdateIn, user: dict = Depends(require_auth)):
    if PERMISSION_MATRIX.get(user["role"], {}).get("user_mgmt") != "full":
        raise HTTPException(403, "Không có quyền quản lý user")
    conn = get_db()
    conn.execute("""UPDATE users SET full_name=?,email=?,phone=?,department=?,
        position=?,skills=?,role=?,status=? WHERE id=?""",
        (body.full_name, body.email, body.phone, body.department,
         body.position, body.skills, body.role, body.status, uid))
    conn.commit(); conn.close()
    log_audit(user, "update", "user", f"Cập nhật user {uid}")
    return {"ok": True}

@app.post("/api/users/{uid}/approve")
def approve_user(uid: str, user: dict = Depends(require_auth)):
    if PERMISSION_MATRIX.get(user["role"], {}).get("user_mgmt") != "full":
        raise HTTPException(403, "Không có quyền duyệt user")
    conn = get_db()
    conn.execute("UPDATE users SET status='active' WHERE id=?", (uid,))
    conn.commit(); conn.close()
    log_audit(user, "approve", "user", f"Duyệt user {uid}")
    return {"ok": True}

@app.delete("/api/users/{uid}")
def delete_user(uid: str, user: dict = Depends(require_auth)):
    if PERMISSION_MATRIX.get(user["role"], {}).get("user_mgmt") != "full":
        raise HTTPException(403, "Không có quyền xóa user")
    conn = get_db()
    conn.execute("DELETE FROM sessions WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()
    return {"ok": True}

@app.get("/api/login-history")
def login_history(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM login_history ORDER BY created_at DESC LIMIT 100").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.get("/api/backups")
def list_backups(user: dict = Depends(require_auth)):
    if PERMISSION_MATRIX.get(user["role"], {}).get("user_mgmt") != "full":
        raise HTTPException(403, "Không có quyền backup")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = []
    for name in sorted(os.listdir(BACKUP_DIR), reverse=True):
        path = os.path.join(BACKUP_DIR, name)
        if os.path.isfile(path):
            st = os.stat(path)
            files.append({"name": name, "size": st.st_size, "created_at": datetime.fromtimestamp(st.st_mtime).isoformat()})
    return files[:30]

@app.post("/api/backups", status_code=201)
def create_backup(user: dict = Depends(require_auth)):
    if PERMISSION_MATRIX.get(user["role"], {}).get("user_mgmt") != "full":
        raise HTTPException(403, "Không có quyền backup")
    os.makedirs(BACKUP_DIR, exist_ok=True)
    name = "autoteam_" + datetime.now().strftime("%Y%m%d_%H%M%S") + ".db"
    dest = os.path.join(BACKUP_DIR, name)
    shutil.copy2(DB_PATH, dest)
    log_audit(user, "backup", "system", name)
    return {"name": name, "path": dest}

@app.get("/api/audit-logs")
def audit_logs(user: dict = Depends(require_auth)):
    conn = get_db()
    rows = conn.execute("SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT 300").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/audit-logs", status_code=201)
def create_audit_log(body: AuditLogIn, user: dict = Depends(require_auth)):
    action = (body.action or "interaction")[:80]
    module = (body.module or "app")[:80]
    detail = (body.detail or "")[:600]
    log_audit(user, action, module, detail)
    return {"ok": True}


if os.path.exists(FRONT_DIR):
    app.mount("/static",StaticFiles(directory=FRONT_DIR,html=True),name="static")

def frontend_index():
    index=os.path.join(FRONT_DIR,"index.html")
    return FileResponse(index) if os.path.exists(index) else JSONResponse({"message":f"AutoTeam PM v{APP_VERSION}"})

@app.get("/",include_in_schema=False)
def root():
    return frontend_index()

@app.get("/dashboard",include_in_schema=False)
@app.get("/tasks",include_in_schema=False)
@app.get("/projects",include_in_schema=False)
@app.get("/phases",include_in_schema=False)
@app.get("/documents",include_in_schema=False)
@app.get("/eoffice",include_in_schema=False)
@app.get("/materials",include_in_schema=False)
@app.get("/bom",include_in_schema=False)
@app.get("/team",include_in_schema=False)
@app.get("/chat",include_in_schema=False)
@app.get("/reports",include_in_schema=False)
@app.get("/admin",include_in_schema=False)
def spa_route():
    return frontend_index()

@app.on_event("startup")
def startup():
    init_db(); seed_db()
    print(f"AutoTeam PM v{APP_VERSION} ready at http://localhost:8000")
