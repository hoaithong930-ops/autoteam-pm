from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional, List
import sqlite3, os, uuid, json
from datetime import date

app = FastAPI(title="AutoTeam PM API", version="2.2.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

BASE_DIR  = os.path.dirname(os.path.abspath(__file__))
DB_PATH   = os.path.join(BASE_DIR, "..", "data", "autoteam.db")
FRONT_DIR = os.path.join(BASE_DIR, "..", "frontend")

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
    """)
    try: c.execute("ALTER TABLE projects ADD COLUMN current_phase TEXT DEFAULT 'Budget Approval'")
    except: pass
    try: c.execute("ALTER TABLE projects ADD COLUMN phase_notes TEXT DEFAULT '{}'")
    except: pass
    conn.commit(); conn.close()

def seed_db():
    conn = get_db(); c = conn.cursor()
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
            ("t1","Lap trinh Function Block valve control","p1","m3","Viet FB cho 24 van","Cao","In Progress","2026-05-28",today_str),
            ("t2","Thiet ke HMI overview platform","p1","m2","SCADA overview","Trung binh","Todo","2026-06-05",today_str),
            ("t3","Review P&ID Rev.3","p1","m4","","Cao","Review",today_str,today_str),
            ("t4","Cau hinh OPC-UA server","p2","m5","","Trung binh","In Progress","2026-06-10",today_str),
            ("t5","Thiet ke wiring diagram MCC 6.6kV","p2","m6","AutoCAD","Thap","Todo","2026-06-20",today_str),
            ("t7","Calibration 45 transmitter","p4","m4","","Trung binh","Done","2026-05-15",today_str),
            ("t8","FAT DCS Cabinet","p4","m1","","Cao","Done","2026-05-10",today_str),
        ]
        c.executemany("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)", tasks)
        docs = [
            ("d1","WHP-A PLC I/O List Rev.04","P&ID","p1","Danh sach I/O","04","Approved","","2026-05-18"),
            ("d2","SCADA Tag Database v2.3","SCADA","p2","Database tag","03","Review","","2026-05-20"),
            ("d3","SIS Logic Diagram","PLC Program","p3","Logic so do","01","Draft","","2026-05-22"),
            ("d4","DCS Wiring Drawing","Wiring","p4","Ban ve wiring","02","Approved","","2026-05-01"),
        ]
        c.executemany("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)", docs)

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
        c.executemany("INSERT INTO inventory_items VALUES (?,?,?,?,?,?,?,?,?,?)", items)

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

class DocumentIn(BaseModel):
    name: str; type: Optional[str]="Khac"; project_id: Optional[str]=""; description: Optional[str]=""
    revision: Optional[str]="01"; status: Optional[str]="Draft"; link: Optional[str]=""

class PhaseUpdate(BaseModel):
    current_phase: str; phase_notes: Optional[str]="{}"

class InventoryItemIn(BaseModel):
    item_code: str; name: str; category: str; description: Optional[str]=""
    unit: Optional[str]="cai"; specs: Optional[str]=""; tags: Optional[str]="[]"

class VendorIn(BaseModel):
    item_id: str; brand: str; model_no: Optional[str]=""; origin: Optional[str]=""
    unit_price: Optional[float]=0; currency: Optional[str]="USD"
    lead_time: Optional[str]=""; datasheet_link: Optional[str]=""
    notes: Optional[str]=""; is_preferred: Optional[int]=0

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
    conn.execute("INSERT INTO inventory_items VALUES (?,?,?,?,?,?,?,?,?,?)",
        (iid, item.item_code, item.name, item.category, item.description,
         item.unit, item.specs, item.tags, now, now))
    conn.commit(); conn.close()
    return {"id": iid}

@app.put("/api/inventory/items/{item_id}")
def update_item(item_id: str, item: InventoryItemIn):
    conn = get_db()
    conn.execute("""UPDATE inventory_items SET item_code=?,name=?,category=?,description=?,
        unit=?,specs=?,tags=?,updated_at=? WHERE id=?""",
        (item.item_code, item.name, item.category, item.description,
         item.unit, item.specs, item.tags, str(date.today()), item_id))
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

@app.get("/api/tasks")
def list_tasks():
    conn=get_db();rows=conn.execute("SELECT t.*,m.name as assignee_name,p.name as project_name FROM tasks t LEFT JOIN members m ON t.assignee_id=m.id LEFT JOIN projects p ON t.project_id=p.id ORDER BY t.created_at DESC").fetchall();conn.close();return[dict(r) for r in rows]

@app.post("/api/tasks",status_code=201)
def create_task(t:TaskIn):
    conn=get_db();tid=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?)",(tid,t.title,t.project_id,t.assignee_id,t.description,t.priority,t.status,t.due_date,str(date.today())))
    conn.commit();conn.close();return{"id":tid}

@app.put("/api/tasks/{tid}")
def update_task(tid:str,t:TaskIn):
    conn=get_db();conn.execute("UPDATE tasks SET title=?,project_id=?,assignee_id=?,description=?,priority=?,status=?,due_date=? WHERE id=?",(t.title,t.project_id,t.assignee_id,t.description,t.priority,t.status,t.due_date,tid));conn.commit();conn.close();return{"ok":True}

@app.delete("/api/tasks/{tid}")
def delete_task(tid:str):
    conn=get_db();conn.execute("DELETE FROM tasks WHERE id=?",(tid,));conn.commit();conn.close();return{"ok":True}

@app.get("/api/documents")
def list_documents():
    conn=get_db();rows=conn.execute("SELECT d.*,p.name as project_name FROM documents d LEFT JOIN projects p ON d.project_id=p.id ORDER BY d.updated_at DESC").fetchall();conn.close();return[dict(r) for r in rows]

@app.post("/api/documents",status_code=201)
def create_document(d:DocumentIn):
    conn=get_db();did=str(uuid.uuid4())[:8]
    conn.execute("INSERT INTO documents VALUES (?,?,?,?,?,?,?,?,?)",(did,d.name,d.type,d.project_id,d.description,d.revision,d.status,d.link,str(date.today())))
    conn.commit();conn.close();return{"id":did}

@app.put("/api/documents/{did}")
def update_document(did:str,d:DocumentIn):
    conn=get_db();conn.execute("UPDATE documents SET name=?,type=?,project_id=?,description=?,revision=?,status=?,link=?,updated_at=? WHERE id=?",(d.name,d.type,d.project_id,d.description,d.revision,d.status,d.link,str(date.today()),did));conn.commit();conn.close();return{"ok":True}

@app.delete("/api/documents/{did}")
def delete_document(did:str):
    conn=get_db();conn.execute("DELETE FROM documents WHERE id=?",(did,));conn.commit();conn.close();return{"ok":True}

@app.get("/api/stats")
def get_stats():
    conn=get_db();c=conn.cursor()
    inv=c.execute("SELECT COUNT(*) FROM inventory_items").fetchone()[0]
    return{"projects":c.execute("SELECT COUNT(*) FROM projects").fetchone()[0],
           "tasks_done":c.execute("SELECT COUNT(*) FROM tasks WHERE status='Done'").fetchone()[0],
           "tasks_open":c.execute("SELECT COUNT(*) FROM tasks WHERE status!='Done'").fetchone()[0],
           "members":c.execute("SELECT COUNT(*) FROM members").fetchone()[0],
           "tasks_today":c.execute("SELECT COUNT(*) FROM tasks WHERE due_date=? AND status!='Done'",(str(date.today()),)).fetchone()[0],
           "inventory_items":inv}

@app.get("/api/phases"); 
def get_phases(): return PHASES

if os.path.exists(FRONT_DIR):
    app.mount("/static",StaticFiles(directory=FRONT_DIR,html=True),name="static")

@app.get("/",include_in_schema=False)
def root():
    index=os.path.join(FRONT_DIR,"index.html")
    return FileResponse(index) if os.path.exists(index) else {"message":"AutoTeam PM v2.2"}

@app.on_event("startup")
def startup():
    init_db(); seed_db()
    print("AutoTeam PM v2.2 ready at http://localhost:8000")
