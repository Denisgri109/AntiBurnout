from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode
from contextlib import asynccontextmanager
import asyncio
import json
import time
import bcrypt
import os
import jwt
import paho.mqtt.client as mqtt
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, HTTPException, status, Depends, Form, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Database import models, schemas
from Database.database import AsyncSessionLocal, Base, engine, get_db

load_dotenv()

# app will crash on startup if these are missing in .env
SECRET_KEY = os.environ["SECRET_KEY"]
PI_SECRET_KEY = os.environ["PI_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    mqtt_client.user_data_set(asyncio.get_running_loop())
    mqtt_client.connect_async(MQTT_BROKER, MQTT_PORT)
    mqtt_client.loop_start()
    yield
    await engine.dispose()

# Hide the API documentation completely
app = FastAPI(
    title="Anti-Burnout",
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
    openapi_url=None
)

FRONTEND_DIRECTORY = Path(__file__).resolve().parent.parent / "Frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIRECTORY), name="static")
templates = Jinja2Templates(directory=FRONTEND_DIRECTORY)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://antiburnout.online"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token structure")

        user_id = int(user_id_str)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Your login has expired, please log in again")

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

async def get_optional_current_user(request: Request, db: Annotated[AsyncSession, Depends(get_db)]):
    try:
        return await get_current_user(request, db)
    except HTTPException:
        return None

async def verify_pi(request: Request):
    api_key = request.headers.get("X-Pi-Secret")
    if not api_key or api_key != PI_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized hardware")


# ---------------------------------------------------------------------------
# Raspberry Pi Connection State
# ---------------------------------------------------------------------------
SENSOR_TOPIC = "antiburnout/sensors/data"
CONTROL_TOPIC = "antiburnout/actuators/control"
PI_TIMEOUT_SECONDS = 5

pi_status = {
    "is_connected": False,
    "pir_connected": False,
    "pressure_connected": False,
    "motion_detected": 0,
    "pressure_detected": 0,
    "pressure_raw": 0.0,
    "error_message": "Pi has not connected yet.",
    "last_seen": None,
}

last_reading_time = 0.0


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code == 0:
        print("Connected to MQTT broker")
        client.subscribe(SENSOR_TOPIC)
    else:
        print(f"Failed to connect to MQTT broker: {reason_code}")


def on_message(client, userdata, msg):
    global last_reading_time
    try:
        pi_status.update(json.loads(msg.payload))
    except (ValueError, TypeError):
        return
    asyncio.run_coroutine_threadsafe(save_sensor_log(pi_status["pressure_detected"], pi_status["motion_detected"]), userdata)
    pi_status["is_connected"] = True
    pi_status["error_message"] = None
    pi_status["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    last_reading_time = time.monotonic()


def pi_is_online():
    if pi_status["is_connected"] and time.monotonic() - last_reading_time > PI_TIMEOUT_SECONDS:
        pi_status["is_connected"] = False
        pi_status["pir_connected"] = False
        pi_status["pressure_connected"] = False
        pi_status["error_message"] = "Raspberry Pi disconnected."
    return pi_status["is_connected"]


async def save_sensor_log(pressure_detected, motion_detected):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(models.Session).where(models.Session.status == "active").order_by(models.Session.id.desc()))
        session = result.scalars().first()
        if not session:
            return

        new_log = models.Sensor_Log(
            session_id=session.id,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            pressure_detected=int(pressure_detected),
            motion_detected=int(motion_detected),
        )
        db.add(new_log)
        await db.commit()


mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
if MQTT_USER and MQTT_PASSWORD:
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message


@app.get("/api/status", dependencies=[Depends(get_current_user)])
async def get_pi_status():
    pi_is_online()
    return pi_status


@app.post("/api/actuator/{device}/{action}")
async def control_actuator(device: str, action: str, current_user: Annotated[models.User, Depends(get_current_user)]):
    if not pi_is_online():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raspberry Pi is not connected",
        )
    mqtt_client.publish(f"{CONTROL_TOPIC}/{device}", json.dumps({"action": action}))
    return {"status": "ok", "device": device, "action": action}

# ---------------------------------------------------------------------------
# Template / Page Routes
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False, name="home")
async def home(
    request: Request,
    current_user: Annotated[models.User | None, Depends(get_optional_current_user)],
):
    return templates.TemplateResponse(request, "index.html", {"title": "Home", "user": current_user})


@app.get("/sensor", include_in_schema=False, name="sensor")
async def sensor_page(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
):
    return templates.TemplateResponse(request, "sensor.html", {"title": "Sensors", "user": current_user})


@app.get("/status", include_in_schema=False, name="status", dependencies=[Depends(get_current_user)])
async def status_page(request: Request):
    return templates.TemplateResponse(request, "Status.html", {"title": "Status"})


@app.get("/contact", include_in_schema=False, name="contact")
async def contact_page(request: Request):
    return templates.TemplateResponse(request, "ContactUs.html", {"title": "Contact"})


@app.get("/login", include_in_schema=False, name="login")
async def login_page(request: Request):
    return templates.TemplateResponse(request, "Login.html", {"title": "Login"})


@app.get("/register", include_in_schema=False, name="register")
async def register_page(request: Request):
    return templates.TemplateResponse(request, "Register.html", {"title": "Register"})


@app.get("/dashboard", include_in_schema=False, name="dashboard")
async def dashboard_page(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    section: str | None = None,
    completed_tasks: Annotated[list[str] | None, Query()] = None,
):

    result = await db.execute(select(models.Session).where(models.Session.user_id == current_user.id))
    sessions = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": current_user,
            "sessions": sessions,
            "title": "User Dashboard",
            "selected_section": section,
            "completed_tasks": completed_tasks or [],
        },
    )

@app.post("/dashboard", include_in_schema=False, name="dashboard_action")
async def dashboard_action(
    request: Request,
    current_user: Annotated[models.User, Depends(get_current_user)],
    section: Annotated[str | None, Form()] = None,
    task_id: Annotated[str | None, Form()] = None,
    completed_tasks: Annotated[list[str] | None, Form()] = None,
):
    tasks = completed_tasks or []
    if task_id is not None:
        if task_id in tasks:
            tasks.remove(task_id)
        else:
            tasks.append(task_id)

    query_values = [("section", section or "tasks")]
    query_values.extend(("completed_tasks", task) for task in tasks)
    query_string = urlencode(query_values)
    return RedirectResponse(
        url=f"/dashboard?{query_string}#tasks",
        status_code=status.HTTP_303_SEE_OTHER,
    )

# ---------------------------------------------------------------------------
# Auth / User Form Submissions
# ---------------------------------------------------------------------------
def create_access_token(user_id: int):
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    # JWT standard expects 'sub' to be a string
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

@app.post("/register", include_in_schema=False)
async def register_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    passwordConfirmation: str = Form(...),
):
    if password != passwordConfirmation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password doesn't match")

    if not 3 <= len(username) <= 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be 3 to 20 characters")

    result = await db.execute(select(models.User).where((models.User.email == email) | (models.User.username == username)))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or Username already exists")

    hashed_password = get_password_hash(password)
    new_user = models.User(username=username, email=email, password_hash=hashed_password)
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=create_access_token(new_user.id), httponly=True, secure=True, samesite="lax")
    return response

@app.post("/login", include_in_schema=False)
async def login_user(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    result = await db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=create_access_token(user.id), httponly=True, secure=True, samesite="lax")
    return response

@app.get("/logout", include_in_schema=False, name="logout")
async def logout_user():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/api/user/{user_id}", response_model=schemas.UserResponse)
async def get_user(user_id: int, db: Annotated[AsyncSession, Depends(get_db)], current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this account")

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

@app.post("/api/sensor_log", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_pi)])
async def create_sensor_log(
    session_id: int,
    pressure_detected: int,
    motion_detected: int,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(select(models.Session).where(models.Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    new_log = models.Sensor_Log(
        session_id=session_id,
        pressure_detected=pressure_detected,
        motion_detected=motion_detected,
    )
    db.add(new_log)
    await db.commit()
    await db.refresh(new_log)
    return new_log


@app.post("/api/session/start", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_pi)])
async def start_session(user_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    new_session = models.Session(
        user_id=user_id,
        start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="active",
    )
    db.add(new_session)
    await db.commit()
    await db.refresh(new_session)
    return new_session

# only the Pi can end sessions
@app.post("/api/session/end/{session_id}", dependencies=[Depends(verify_pi)])
async def end_session(session_id: int, db: Annotated[AsyncSession, Depends(get_db)]):
    result = await db.execute(select(models.Session).where(models.Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session.status = "completed"
    await db.commit()
    await db.refresh(session)
    return session



def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)
    message = exception.detail if exception.detail else "An error occurred. Please check your request and try again"
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": exception.status_code, "title": exception.status_code, "message": message},
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Please check your input and try again",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
