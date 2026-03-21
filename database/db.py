# database/db.py — PostgreSQL + SQLite fallback
from config import SLOT_DURATION, DEFAULT_SERVICES, TIMEZONE, USE_POSTGRES
from datetime import datetime
import pytz, logging

logger = logging.getLogger(__name__)
_pool = None


def _now_local() -> str:
    return datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")

def _today_local() -> str:
    return datetime.now(pytz.timezone(TIMEZONE)).strftime("%Y-%m-%d")


async def init_db():
    global _pool
    if USE_POSTGRES:
        await _init_postgres()
    else:
        await _init_sqlite()
    await seed_services()
    await seed_settings()


# ── PostgreSQL ────────────────────────────────────────────────────────

async def _init_postgres():
    global _pool
    import asyncpg, os
    from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD, DB_POOL_SIZE, DATABASE_URL
    dsn = DATABASE_URL or f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    _pool = await asyncpg.create_pool(dsn=dsn, min_size=2, max_size=DB_POOL_SIZE)
    sql_file = os.path.join(os.path.dirname(__file__), '..', 'migrations', '001_initial.sql')
    if os.path.exists(sql_file):
        async with _pool.acquire() as c:
            await c.execute(open(sql_file).read())
    logger.info("PostgreSQL ready")


class _PG:
    def __init__(self): self._c = None
    async def __aenter__(self):
        self._c = await _pool.acquire(); return self._c
    async def __aexit__(self, *a): await _pool.release(self._c)

def pg(): return _PG()


# ── SQLite ────────────────────────────────────────────────────────────

async def _init_sqlite():
    import aiosqlite
    from config import DB_PATH
    async with aiosqlite.connect(DB_PATH) as d:
        await d.executescript("""
            CREATE TABLE IF NOT EXISTS schedule(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL, time_slot TEXT NOT NULL,
                is_booked INTEGER DEFAULT 0, is_closed INTEGER DEFAULT 0,
                UNIQUE(date,time_slot));
            CREATE TABLE IF NOT EXISTS appointments(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, username TEXT,
                client_name TEXT NOT NULL, phone TEXT NOT NULL DEFAULT '—',
                date TEXT NOT NULL, time_slot TEXT NOT NULL,
                service_key TEXT DEFAULT '', service_name TEXT DEFAULT '',
                service_price INTEGER DEFAULT 0, slots_count INTEGER DEFAULT 1,
                attended INTEGER DEFAULT NULL,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                reminder_job_id TEXT, repeat_job_id TEXT, master_job_id TEXT);
            CREATE TABLE IF NOT EXISTS services(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL, name TEXT NOT NULL,
                price INTEGER NOT NULL DEFAULT 0, slots INTEGER NOT NULL DEFAULT 1,
                duration_str TEXT DEFAULT '', emoji TEXT DEFAULT '💅',
                repeat_days INTEGER DEFAULT 0, is_active INTEGER DEFAULT 1);
            CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS blacklist(
                user_id INTEGER PRIMARY KEY, username TEXT, client_name TEXT,
                reason TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now','localtime')));
        """)
        for col, dfn in [("phone","TEXT NOT NULL DEFAULT '—'"),
                         ("attended","INTEGER DEFAULT NULL"),
                         ("repeat_job_id","TEXT"),("master_job_id","TEXT")]:
            try: await d.execute(f"ALTER TABLE appointments ADD COLUMN {col} {dfn}")
            except: pass
        await d.commit()


# ── Универсальный адаптер ─────────────────────────────────────────────

def _pg(sql):
    i=0; r=[]
    for c in sql:
        if c=='?': i+=1; r.append(f'${i}')
        else: r.append(c)
    return ''.join(r)


class _Conn:
    def __init__(self, c, is_pg): self._c=c; self._pg=is_pg
    async def one(self, sql, *a):
        if self._pg: return await self._c.fetchrow(_pg(sql),*a)
        cur=await self._c.execute(sql,a); return await cur.fetchone()
    async def all(self, sql, *a):
        if self._pg: return await self._c.fetch(_pg(sql),*a)
        cur=await self._c.execute(sql,a); return await cur.fetchall()
    async def run(self, sql, *a):
        if self._pg: await self._c.execute(_pg(sql),*a)
        else: await self._c.execute(sql,a); await self._c.commit()
    async def val(self, sql, *a):
        if self._pg: return await self._c.fetchval(_pg(sql),*a)
        cur=await self._c.execute(sql,a); r=await cur.fetchone(); return r[0] if r else None


class _Ctx:
    def __init__(self): self._c=None; self._sl=None
    async def __aenter__(self):
        if USE_POSTGRES:
            self._c=await _pool.acquire(); return _Conn(self._c,True)
        import aiosqlite
        from config import DB_PATH
        self._sl=aiosqlite.connect(DB_PATH)
        c=await self._sl.__aenter__(); return _Conn(c,False)
    async def __aexit__(self,*a):
        if USE_POSTGRES: await _pool.release(self._c)
        else: await self._sl.__aexit__(*a)

def db(): return _Ctx()


# ── Настройки ─────────────────────────────────────────────────────────

async def get_setting(key):
    async with db() as c: r=await c.one("SELECT value FROM settings WHERE key=?",key)
    return r[0] if r else "0"

async def set_setting(key, value):
    async with db() as c:
        if USE_POSTGRES:
            await c.run("INSERT INTO settings(key,value) VALUES(?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=EXCLUDED.value", key, value)
        else:
            await c.run("INSERT OR REPLACE INTO settings(key,value) VALUES(?,?)", key, value)

async def seed_settings():
    defs = {"repeat_reminders_enabled":"1","master_30min_enabled":"1",
            "dense_schedule":"0","loyalty_enabled":"0","loyalty_mode":"discount",
            "loyalty_visits":"3","loyalty_discount":"10"}
    async with db() as c:
        for k,v in defs.items():
            if USE_POSTGRES:
                await c.run("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT DO NOTHING",k,v)
            else:
                await c.run("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)",k,v)


# ── Услуги ────────────────────────────────────────────────────────────

async def get_services(active_only=True):
    q="SELECT id,key,name,price,slots,duration_str,emoji,repeat_days,is_active FROM services"
    if active_only: q+=" WHERE is_active=TRUE" if USE_POSTGRES else " WHERE is_active=1"
    q+=" ORDER BY id"
    async with db() as c: rows=await c.all(q)
    return [{"id":r[0],"key":r[1],"name":r[2],"price":r[3],"slots":r[4],
             "duration_str":r[5],"emoji":r[6],"repeat_days":r[7],"is_active":bool(r[8])} for r in rows]

async def get_service_by_key(key):
    async with db() as c:
        r=await c.one("SELECT id,key,name,price,slots,duration_str,emoji,repeat_days,is_active "
                      "FROM services WHERE key=?",key)
    if not r: return None
    return {"id":r[0],"key":r[1],"name":r[2],"price":r[3],"slots":r[4],
            "duration_str":r[5],"emoji":r[6],"repeat_days":r[7],"is_active":bool(r[8])}

async def add_service(key,name,price,slots,duration_str,emoji,repeat_days):
    try:
        async with db() as c:
            await c.run("INSERT INTO services(key,name,price,slots,duration_str,emoji,repeat_days) "
                        "VALUES(?,?,?,?,?,?,?)",key,name,price,slots,duration_str,emoji,repeat_days)
        return True
    except: return False

async def update_service(svc_id,name,price,slots,duration_str,emoji,repeat_days):
    async with db() as c:
        await c.run("UPDATE services SET name=?,price=?,slots=?,duration_str=?,emoji=?,repeat_days=? "
                    "WHERE id=?",name,price,slots,duration_str,emoji,repeat_days,svc_id)

async def toggle_service(svc_id):
    async with db() as c:
        if USE_POSTGRES: await c.run("UPDATE services SET is_active=NOT is_active WHERE id=?",svc_id)
        else: await c.run("UPDATE services SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?",svc_id)

async def seed_services():
    async with db() as c:
        r=await c.one("SELECT COUNT(*) FROM services"); count=r[0] if r else 0
        if count==0:
            for s in DEFAULT_SERVICES:
                if USE_POSTGRES:
                    await c.run("INSERT INTO services(key,name,price,slots,duration_str,emoji,repeat_days) "
                                "VALUES(?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
                                s["key"],s["name"],s["price"],s["slots"],s["duration_str"],s["emoji"],s.get("repeat_days",0))
                else:
                    await c.run("INSERT OR IGNORE INTO services(key,name,price,slots,duration_str,emoji,repeat_days) "
                                "VALUES(?,?,?,?,?,?,?)",
                                s["key"],s["name"],s["price"],s["slots"],s["duration_str"],s["emoji"],s.get("repeat_days",0))


# ── Расписание ────────────────────────────────────────────────────────

def generate_slots(start_time, end_time):
    slots=[]; sh,sm=map(int,start_time.split(":")); eh,em=map(int,end_time.split(":"))
    cur=sh*60+sm; end=eh*60+em
    while cur<end: h,m=divmod(cur,60); slots.append(f"{h:02d}:{m:02d}"); cur+=SLOT_DURATION
    return slots

async def add_working_day(date, start_time, end_time):
    slots=generate_slots(start_time,end_time); added=0
    async with db() as c:
        for s in slots:
            try:
                if USE_POSTGRES:
                    await c.run("INSERT INTO schedule(date,time_slot) VALUES(?,?) ON CONFLICT DO NOTHING",date,s)
                else:
                    await c.run("INSERT OR IGNORE INTO schedule(date,time_slot) VALUES(?,?)",date,s)
                added+=1
            except: pass
    return added

async def add_slot(date, time_slot):
    try:
        async with db() as c:
            if USE_POSTGRES: await c.run("INSERT INTO schedule(date,time_slot) VALUES(?,?) ON CONFLICT DO NOTHING",date,time_slot)
            else: await c.run("INSERT OR IGNORE INTO schedule(date,time_slot) VALUES(?,?)",date,time_slot)
        return True
    except: return False

async def remove_slot(date, time_slot):
    async with db() as c:
        r=await c.one("SELECT is_booked FROM schedule WHERE date=? AND time_slot=?",date,time_slot)
        if not r or r[0]: return False
        await c.run("DELETE FROM schedule WHERE date=? AND time_slot=?",date,time_slot)
    return True

async def close_day(date):
    async with db() as c:
        if USE_POSTGRES: await c.run("UPDATE schedule SET is_closed=TRUE WHERE date=? AND is_booked=FALSE",date)
        else: await c.run("UPDATE schedule SET is_closed=1 WHERE date=? AND is_booked=0",date)

async def open_day(date):
    async with db() as c:
        if USE_POSTGRES: await c.run("UPDATE schedule SET is_closed=FALSE WHERE date=?",date)
        else: await c.run("UPDATE schedule SET is_closed=0 WHERE date=?",date)

async def get_available_dates():
    now=_now_local(); today=_today_local()
    async with db() as c:
        if USE_POSTGRES:
            rows=await c.all("""SELECT DISTINCT date FROM schedule
                WHERE is_booked=FALSE AND is_closed=FALSE
                AND (date||' '||time_slot)>? AND date::date<(?::date+'31 days'::interval)
                ORDER BY date""",now,today)
        else:
            rows=await c.all("""SELECT DISTINCT date FROM schedule
                WHERE is_booked=0 AND is_closed=0
                AND (date||' '||time_slot)>? AND date<date(?,'+'||31||' days')
                ORDER BY date""",now,today)
    return [r[0] for r in rows]

async def get_slots_for_date(date):
    async with db() as c:
        rows=await c.all("SELECT time_slot,is_booked,is_closed FROM schedule WHERE date=? ORDER BY time_slot",date)
    return [{"time":r[0],"is_booked":bool(r[1]),"is_closed":bool(r[2])} for r in rows]

async def get_free_slots(date):
    async with db() as c:
        if USE_POSTGRES:
            rows=await c.all("SELECT time_slot FROM schedule WHERE date=? AND is_booked=FALSE AND is_closed=FALSE ORDER BY time_slot",date)
        else:
            rows=await c.all("SELECT time_slot FROM schedule WHERE date=? AND is_booked=0 AND is_closed=0 ORDER BY time_slot",date)
    return [r[0] for r in rows]

async def get_free_slots_for_service(date, slots_needed):
    free=await get_free_slots(date)
    if slots_needed<=1: return free
    free_set=set(free); result=[]
    for start in free:
        h,m=map(int,start.split(":")); ok=True
        for i in range(1,slots_needed):
            total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
            if slot not in free_set: ok=False; break
        if ok: result.append(start)
    return result


# ── Записи ────────────────────────────────────────────────────────────

async def get_user_appointment(user_id):
    async with db() as c:
        r=await c.one("SELECT id,date,time_slot,client_name,phone,reminder_job_id,"
                      "service_name,service_price,slots_count,service_key "
                      "FROM appointments WHERE user_id=? AND (date||' '||time_slot)>=? "
                      "ORDER BY date,time_slot LIMIT 1", user_id, _now_local())
    if r: return {"id":r[0],"date":r[1],"time_slot":r[2],"client_name":r[3],"phone":r[4],
                  "reminder_job_id":r[5],"service_name":r[6],"service_price":r[7],
                  "slots_count":r[8],"service_key":r[9]}
    return None


async def create_appointment(user_id, username, client_name, phone, date, time_slot,
                              service_key="", service_name="", service_price=0, slots_count=1):
    try:
        if USE_POSTGRES:
            async with pg() as conn:
                async with conn.transaction():
                    h,m=map(int,time_slot.split(":"))
                    for i in range(slots_count):
                        total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        r=await conn.fetchrow(
                            "SELECT is_booked,is_closed FROM schedule WHERE date=$1 AND time_slot=$2 FOR UPDATE",
                            date,slot)
                        if not r or r[0] or r[1]: raise Exception("unavailable")
                    for i in range(slots_count):
                        total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        await conn.execute("UPDATE schedule SET is_booked=TRUE WHERE date=$1 AND time_slot=$2",date,slot)
                    return await conn.fetchval(
                        "INSERT INTO appointments(user_id,username,client_name,phone,date,time_slot,"
                        "service_key,service_name,service_price,slots_count) "
                        "VALUES($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
                        user_id,username,client_name,phone,date,time_slot,
                        service_key,service_name,service_price,slots_count)
        else:
            import aiosqlite
            from config import DB_PATH
            async with aiosqlite.connect(DB_PATH) as d:
                await d.execute("BEGIN EXCLUSIVE")
                h,m=map(int,time_slot.split(":"))
                for i in range(slots_count):
                    total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    cur=await d.execute("SELECT is_booked,is_closed FROM schedule WHERE date=? AND time_slot=?",(date,slot))
                    r=await cur.fetchone()
                    if not r or r[0]==1 or r[1]==1: await d.execute("ROLLBACK"); return None
                for i in range(slots_count):
                    total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    await d.execute("UPDATE schedule SET is_booked=1 WHERE date=? AND time_slot=?",(date,slot))
                cur=await d.execute(
                    "INSERT INTO appointments(user_id,username,client_name,phone,date,time_slot,"
                    "service_key,service_name,service_price,slots_count) VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (user_id,username,client_name,phone,date,time_slot,service_key,service_name,service_price,slots_count))
                appt_id=cur.lastrowid; await d.execute("COMMIT"); return appt_id
    except: return None


async def cancel_appointment(appointment_id):
    try:
        if USE_POSTGRES:
            async with pg() as conn:
                async with conn.transaction():
                    r=await conn.fetchrow(
                        "SELECT user_id,date,time_slot,reminder_job_id,slots_count,"
                        "repeat_job_id,master_job_id FROM appointments WHERE id=$1 FOR UPDATE",
                        appointment_id)
                    if not r: return None
                    uid,date,ts,rjid,sc,rpjid,mjid=r[0],r[1],r[2],r[3],r[4],r[5],r[6]; sc=sc or 1
                    h,m=map(int,ts.split(":"))
                    for i in range(sc):
                        total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        await conn.execute("UPDATE schedule SET is_booked=FALSE WHERE date=$1 AND time_slot=$2",date,slot)
                    await conn.execute("DELETE FROM appointments WHERE id=$1",appointment_id)
        else:
            import aiosqlite
            from config import DB_PATH
            async with aiosqlite.connect(DB_PATH) as d:
                await d.execute("BEGIN EXCLUSIVE")
                cur=await d.execute("SELECT user_id,date,time_slot,reminder_job_id,slots_count,"
                                    "repeat_job_id,master_job_id FROM appointments WHERE id=?",(appointment_id,))
                r=await cur.fetchone()
                if not r: await d.execute("ROLLBACK"); return None
                uid,date,ts,rjid,sc,rpjid,mjid=r; sc=sc or 1
                h,m=map(int,ts.split(":"))
                for i in range(sc):
                    total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    await d.execute("UPDATE schedule SET is_booked=0 WHERE date=? AND time_slot=?",(date,slot))
                await d.execute("DELETE FROM appointments WHERE id=?",(appointment_id,))
                await d.execute("COMMIT")
        return {"user_id":uid,"date":date,"time_slot":ts,
                "reminder_job_id":rjid,"repeat_job_id":rpjid,"master_job_id":mjid}
    except: return None


async def get_appointment_by_id(appointment_id):
    async with db() as c:
        r=await c.one("SELECT id,user_id,date,time_slot,client_name,service_name,service_key,slots_count "
                      "FROM appointments WHERE id=?",appointment_id)
    if not r: return None
    return {"id":r[0],"user_id":r[1],"date":r[2],"time_slot":r[3],
            "client_name":r[4],"service_name":r[5],"service_key":r[6],"slots_count":r[7] or 1}

async def cancel_appointment_by_user(user_id):
    a=await get_user_appointment(user_id)
    return await cancel_appointment(a["id"]) if a else None

async def reschedule_appointment(appointment_id, new_date, new_time_slot):
    try:
        if USE_POSTGRES:
            async with pg() as conn:
                async with conn.transaction():
                    r=await conn.fetchrow(
                        "SELECT user_id,date,time_slot,slots_count,reminder_job_id,"
                        "repeat_job_id,master_job_id,client_name,service_name "
                        "FROM appointments WHERE id=$1 FOR UPDATE",appointment_id)
                    if not r: return None
                    uid,od,os_,sc,rjid,rpjid,mjid,cn,sn=r; sc=sc or 1
                    h,m=map(int,new_time_slot.split(":"))
                    for i in range(sc):
                        total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        nr=await conn.fetchrow("SELECT is_booked,is_closed FROM schedule WHERE date=$1 AND time_slot=$2 FOR UPDATE",new_date,slot)
                        if not nr or nr[0] or nr[1]: raise Exception("unavailable")
                    oh,om_=map(int,os_.split(":"))
                    for i in range(sc):
                        total=oh*60+om_+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        await conn.execute("UPDATE schedule SET is_booked=FALSE WHERE date=$1 AND time_slot=$2",od,slot)
                    for i in range(sc):
                        total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                        await conn.execute("UPDATE schedule SET is_booked=TRUE WHERE date=$1 AND time_slot=$2",new_date,slot)
                    await conn.execute("UPDATE appointments SET date=$1,time_slot=$2 WHERE id=$3",new_date,new_time_slot,appointment_id)
        else:
            import aiosqlite
            from config import DB_PATH
            async with aiosqlite.connect(DB_PATH) as d:
                await d.execute("BEGIN EXCLUSIVE")
                cur=await d.execute("SELECT user_id,date,time_slot,slots_count,reminder_job_id,"
                                    "repeat_job_id,master_job_id,client_name,service_name FROM appointments WHERE id=?",(appointment_id,))
                r=await cur.fetchone()
                if not r: await d.execute("ROLLBACK"); return None
                uid,od,os_,sc,rjid,rpjid,mjid,cn,sn=r; sc=sc or 1
                h,m=map(int,new_time_slot.split(":"))
                for i in range(sc):
                    total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    cur=await d.execute("SELECT is_booked,is_closed FROM schedule WHERE date=? AND time_slot=?",(new_date,slot))
                    nr=await cur.fetchone()
                    if not nr or nr[0]==1 or nr[1]==1: await d.execute("ROLLBACK"); return None
                oh,om_=map(int,os_.split(":"))
                for i in range(sc):
                    total=oh*60+om_+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    await d.execute("UPDATE schedule SET is_booked=0 WHERE date=? AND time_slot=?",(od,slot))
                for i in range(sc):
                    total=h*60+m+i*SLOT_DURATION; slot=f"{total//60:02d}:{total%60:02d}"
                    await d.execute("UPDATE schedule SET is_booked=1 WHERE date=? AND time_slot=?",(new_date,slot))
                await d.execute("UPDATE appointments SET date=?,time_slot=? WHERE id=?",(new_date,new_time_slot,appointment_id))
                await d.execute("COMMIT")
        return {"user_id":uid,"slots_count":sc,"old_date":od,"old_slot":os_,
                "new_date":new_date,"new_slot":new_time_slot,
                "reminder_job_id":rjid,"repeat_job_id":rpjid,"master_job_id":mjid,
                "client_name":cn,"service_name":sn}
    except: return None

async def save_job_ids(appointment_id, reminder_job_id=None, repeat_job_id=None, master_job_id=None):
    async with db() as c:
        if reminder_job_id is not None: await c.run("UPDATE appointments SET reminder_job_id=? WHERE id=?",reminder_job_id,appointment_id)
        if repeat_job_id is not None:   await c.run("UPDATE appointments SET repeat_job_id=? WHERE id=?",repeat_job_id,appointment_id)
        if master_job_id is not None:   await c.run("UPDATE appointments SET master_job_id=? WHERE id=?",master_job_id,appointment_id)

async def mark_attendance(appointment_id, attended):
    async with db() as c:
        await c.run("UPDATE appointments SET attended=? WHERE id=?",int(attended),appointment_id)

async def get_schedule_for_date(date):
    async with db() as c:
        rows=await c.all("""SELECT s.time_slot,s.is_booked,s.is_closed,
               a.client_name,a.phone,a.username,a.user_id,a.id,a.service_name,a.service_price
               FROM schedule s LEFT JOIN appointments a ON a.date=s.date AND a.time_slot=s.time_slot
               WHERE s.date=? ORDER BY s.time_slot""",date)
    return [{"time":r[0],"is_booked":bool(r[1]),"is_closed":bool(r[2]),
             "client_name":r[3],"phone":r[4],"username":r[5],
             "user_id":r[6],"appt_id":r[7],"service_name":r[8] or "","service_price":r[9] or 0} for r in rows]

async def get_all_future_appointments():
    async with db() as c:
        rows=await c.all("SELECT id,user_id,client_name,date,time_slot,reminder_job_id,"
                         "slots_count,service_name,service_key FROM appointments "
                         "WHERE date>=? ORDER BY date,time_slot",_today_local())
    return [{"id":r[0],"user_id":r[1],"client_name":r[2],"date":r[3],
             "time_slot":r[4],"reminder_job_id":r[5],"slots_count":r[6],
             "service_name":r[7],"service_key":r[8]} for r in rows]

async def get_appointments_for_date(date):
    async with db() as c:
        rows=await c.all("SELECT time_slot,client_name,phone,service_name FROM appointments WHERE date=? ORDER BY time_slot",date)
    return [{"time":r[0],"client_name":r[1],"phone":r[2],"service_name":r[3] or ""} for r in rows]

async def create_manual_appointment(client_name, phone, date, time_slot,
                                    service_key="", service_name="", service_price=0, slots_count=1):
    return await create_appointment(0,"manual",client_name,phone,date,time_slot,
                                    service_key,service_name,service_price,slots_count)


# ── Статистика ────────────────────────────────────────────────────────

async def get_stats_month(year, month):
    pat=f"{year:04d}-{month:02d}-%"
    async with db() as c:
        r=await c.one("""SELECT COUNT(*),COUNT(DISTINCT CASE WHEN user_id!=0 THEN user_id END),
            SUM(service_price),SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN attended=0 THEN 1 ELSE 0 END) FROM appointments WHERE date LIKE ?""",pat)
        total,uc,rev,att,ns=r[0],r[1],r[2] or 0,r[3],r[4]
        nc=await c.val("SELECT COUNT(*) FROM (SELECT user_id,MIN(date) fd FROM appointments "
                       "WHERE user_id!=0 GROUP BY user_id HAVING MIN(date) LIKE ?) t",pat)
        by_day=await c.all("SELECT date,COUNT(*) FROM appointments WHERE date LIKE ? GROUP BY date ORDER BY date",pat)
        by_svc=await c.all("SELECT service_name,COUNT(*) FROM appointments WHERE date LIKE ? AND service_name!='' GROUP BY service_name ORDER BY 2 DESC",pat)
        tc=await c.val("SELECT COUNT(DISTINCT user_id) FROM appointments WHERE user_id!=0")
    return {"total":total,"unique_clients":uc,"new_clients":nc or 0,
            "busiest_day":max(by_day,key=lambda x:x[1]) if by_day else None,
            "total_clients_ever":tc or 0,"by_day":by_day,"revenue":rev,
            "by_service":by_svc,"attended":att,"no_show":ns}

async def get_stats_alltime():
    async with db() as c:
        r=await c.one("""SELECT COUNT(*),COUNT(DISTINCT CASE WHEN user_id!=0 THEN user_id END),
            SUM(service_price),SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END),
            SUM(CASE WHEN attended=0 THEN 1 ELSE 0 END) FROM appointments""")
        total,uc,rev,att,ns=r[0],r[1],r[2] or 0,r[3],r[4]
        busiest=await c.one("SELECT date,COUNT(*) FROM appointments GROUP BY date ORDER BY 2 DESC LIMIT 1")
        if USE_POSTGRES:
            by_month=await c.all("SELECT TO_CHAR(date::date,'YYYY-MM'),COUNT(*) FROM appointments GROUP BY 1 ORDER BY 1 DESC LIMIT 6")
        else:
            by_month=await c.all("SELECT strftime('%Y-%m',date),COUNT(*) FROM appointments GROUP BY 1 ORDER BY 1 DESC LIMIT 6")
        by_svc=await c.all("SELECT service_name,COUNT(*) FROM appointments WHERE service_name!='' GROUP BY service_name ORDER BY 2 DESC")
    return {"total":total,"unique_clients":uc,"busiest_day":busiest,"by_month":by_month,
            "revenue":rev,"by_service":by_svc,"attended":att,"no_show":ns}

async def get_all_user_ids():
    async with db() as c: rows=await c.all("SELECT DISTINCT user_id FROM appointments WHERE user_id!=0")
    return [r[0] for r in rows]

async def get_client_stats(user_id):
    async with db() as c:
        r=await c.one("SELECT COUNT(*),SUM(CASE WHEN attended=1 THEN 1 ELSE 0 END),MAX(date) "
                      "FROM appointments WHERE user_id=? AND (date||' '||time_slot)<?",user_id,_now_local())
    return {"total":r[0] or 0,"confirmed":r[1] or 0,"last_date":r[2] or ""}


# ── Чёрный список ─────────────────────────────────────────────────────

async def blacklist_add(user_id, username="", client_name="", reason=""):
    async with db() as c:
        if USE_POSTGRES:
            await c.run("INSERT INTO blacklist(user_id,username,client_name,reason) VALUES(?,?,?,?) "
                        "ON CONFLICT(user_id) DO UPDATE SET username=EXCLUDED.username,"
                        "client_name=EXCLUDED.client_name,reason=EXCLUDED.reason",
                        user_id,username,client_name,reason)
        else:
            await c.run("INSERT OR REPLACE INTO blacklist(user_id,username,client_name,reason) VALUES(?,?,?,?)",
                        user_id,username,client_name,reason)

async def blacklist_remove(user_id):
    async with db() as c: await c.run("DELETE FROM blacklist WHERE user_id=?",user_id)

async def blacklist_check(user_id):
    async with db() as c: r=await c.one("SELECT 1 FROM blacklist WHERE user_id=?",user_id)
    return r is not None

async def blacklist_get_all():
    async with db() as c:
        rows=await c.all("SELECT user_id,username,client_name,reason FROM blacklist ORDER BY created_at DESC")
    return [{"user_id":r[0],"username":r[1],"client_name":r[2],"reason":r[3]} for r in rows]
