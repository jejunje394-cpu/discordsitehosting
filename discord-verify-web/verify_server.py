import uuid, datetime
import aiosqlite, httpx
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from user_agents import parse as ua_parse

app = FastAPI()
DB = "auth.db"

IPINFO_TOKEN = "5213ee4451d0fa"

@app.on_event("startup")
async def startup():
    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS logs (
            id TEXT,
            discord_id TEXT,
            email TEXT,
            ip TEXT,
            country TEXT,
            region TEXT,
            city TEXT,
            os TEXT,
            browser TEXT,
            time TEXT
        )
        """)
        await db.commit()

@app.get("/verify", response_class=HTMLResponse)
async def verify_page(discord_id: str):
    return f"""
    <h2>🔐 디스코드 인증</h2>
    <form method="post">
      <input type="hidden" name="discord_id" value="{discord_id}">
      이메일: <input name="email" required><br><br>
      <input type="checkbox" required> 개인정보 수집 및 이용에 동의합니다<br><br>
      <button>인증</button>
    </form>
    """

@app.post("/verify")
async def verify(request: Request,
                 discord_id: str = Form(...),
                 email: str = Form(...)):

    ip = request.client.host

    async with httpx.AsyncClient() as client:
        r = await client.get(f"https://ipinfo.io/{ip}?token={IPINFO_TOKEN}")
        info = r.json()

    ua = ua_parse(request.headers.get("user-agent", ""))

    log_id = str(uuid.uuid4())
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    async with aiosqlite.connect(DB) as db:
        await db.execute("""
        INSERT INTO logs VALUES (?,?,?,?,?,?,?,?,?,?)
        """, (
            log_id,
            discord_id,
            email,
            ip,
            info.get("country"),
            info.get("region"),
            info.get("city"),
            ua.os.family,
            ua.browser.family,
            now
        ))
        await db.commit()

    return RedirectResponse("/success", status_code=302)

@app.get("/success", response_class=HTMLResponse)
async def success():
    return "<h2>✅ 인증 성공</h2> 디스코드로 돌아가세요."

@app.get("/api/check")
async def check(discord_id: str):
    async with aiosqlite.connect(DB) as db:
        row = await db.execute_fetchone(
            "SELECT * FROM logs WHERE discord_id=? ORDER BY time DESC",
            (discord_id,)
        )

    if not row:
        return JSONResponse({"verified": False})

    return {
        "verified": True,
        "email": row[2],
        "ip": row[3],
        "country": row[4],
        "region": row[5],
        "city": row[6],
        "os": row[7],
        "browser": row[8],
        "time": row[9],
        "log_id": row[0]
    }