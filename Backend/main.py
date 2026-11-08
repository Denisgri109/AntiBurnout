from pathlib import Path
from typing import Annotated
from urllib.parse import urlencode
import json
import bcrypt
import os
import jwt
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI, Request, HTTPException, status, Depends, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from Database import models, schemas
from Database.database import Base, engine, get_db

load_dotenv()

# app will crash on startup if these are missing in .env
SECRET_KEY = os.environ["SECRET_KEY"]
PI_SECRET_KEY = os.environ["PI_SECRET_KEY"]
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Create database tables
Base.metadata.create_all(bind=engine)

# Hide the API documentation completely
app = FastAPI(
    title="Anti-Burnout",
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

def get_current_user(request: Request, db: Annotated[Session, Depends(get_db)]):
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

    user = db.execute(select(models.User).where(models.User.id == user_id)).scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user

def verify_pi(request: Request):
    api_key = request.headers.get("X-Pi-Secret")
    if not api_key or api_key != PI_SECRET_KEY:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized hardware")


# ---------------------------------------------------------------------------
# Raspberry Pi Connection State
# ---------------------------------------------------------------------------
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

pi_socket: WebSocket | None = None


@app.websocket("/ws/pi")
async def pi_endpoint(websocket: WebSocket):
    # Check headers securely so the key isn't in the URL
    pi_secret = websocket.headers.get("X-Pi-Secret")
    if pi_secret != PI_SECRET_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    global pi_socket, pi_status
    await websocket.accept()
    pi_socket = websocket
    pi_status["is_connected"] = True
    pi_status["pir_connected"] = True
    pi_status["pressure_connected"] = True
    pi_status["error_message"] = None

    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                pi_status.update(payload)
            except json.JSONDecodeError:
                pass
            pi_status["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    except WebSocketDisconnect:
        pi_status["is_connected"] = False
        pi_status["pir_connected"] = False
        pi_status["pressure_connected"] = False
        pi_status["error_message"] = "Raspberry Pi disconnected."
    except Exception as e:
        pi_status["is_connected"] = False
        pi_status["error_message"] = f"Error: {str(e)}"
    finally:
        pi_socket = None

@app.get("/api/status", dependencies=[Depends(get_current_user)])
def get_pi_status():
    return pi_status


# Only logged-in web users can hit this endpoint
@app.post("/api/actuator/{device}/{action}")
async def control_actuator(device: str, action: str, current_user: Annotated[models.User, Depends(get_current_user)]):
    if not pi_socket:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Raspberry Pi is not connected",
        )
    await pi_socket.send_text(json.dumps({"device": device, "action": action}))
    return {"status": "ok", "device": device, "action": action}

# ---------------------------------------------------------------------------
# Template / Page Routes
# ---------------------------------------------------------------------------
@app.get("/", include_in_schema=False, name="home")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"title": "Home"})


@app.get("/sensor", include_in_schema=False, name="sensor", dependencies=[Depends(get_current_user)])
def sensor_page(request: Request):
    return templates.TemplateResponse(request, "sensor.html", {"title": "Sensors"})


@app.get("/status", include_in_schema=False, name="status", dependencies=[Depends(get_current_user)])
def status_page(request: Request):
    return templates.TemplateResponse(request, "Status.html", {"title": "Status"})


@app.get("/contact", include_in_schema=False, name="contact")
def contact_page(request: Request):
    return templates.TemplateResponse(request, "ContactUs.html", {"title": "Contact"})


@app.get("/login", include_in_schema=False, name="login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "Login.html", {"title": "Login"})


@app.get("/register", include_in_schema=False, name="register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "Register.html", {"title": "Register"})


@app.get("/dashboard", include_in_schema=False, name="dashboard")
def dashboard_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    current_user: Annotated[models.User, Depends(get_current_user)],
    section: str | None = None,
    completed_tasks: Annotated[list[str] | None, Query()] = None,
):
    # Only fetches sessions belonging to the logged-in user
    sessions = db.execute(select(models.Session).where(models.Session.user_id == current_user.id)).scalars().all()

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
def dashboard_action(
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
def register_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    passwordConfirmation: str = Form(...),
):
    if password != passwordConfirmation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password doesn't match")

    if not 3 <= len(username) <= 20:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username must be 3 to 20 characters")

    # This stops the crash. checks for duplicates before creating
    existing_user = db.execute(select(models.User).where((models.User.email == email) | (models.User.username == username))).scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email or Username already exists")

    hashed_password = get_password_hash(password)
    new_user = models.User(username=username, email=email, password_hash=hashed_password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=create_access_token(new_user.id), httponly=True, secure=True, samesite="lax")
    return response

@app.post("/login", include_in_schema=False)
def login_user(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    email: str = Form(...),
    password: str = Form(...),
):
    user = db.execute(select(models.User).where(models.User.email == email)).scalars().first()
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
        )

    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="access_token", value=create_access_token(user.id), httponly=True, secure=True, samesite="lax")
    return response

@app.get("/logout", include_in_schema=False, name="logout")
def logout_user():
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie("access_token")
    return response

@app.get("/api/user/{user_id}", response_model=schemas.UserResponse)
def get_user(user_id: int, db: Annotated[Session, Depends(get_db)], current_user: Annotated[models.User, Depends(get_current_user)]):
    if current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this account")

    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

@app.post("/api/sensor_log", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_pi)])
def create_sensor_log(
    session_id: int,
    pressure_detected: int,
    motion_detected: int,
    db: Annotated[Session, Depends(get_db)],
):
    result = db.execute(select(models.Session).where(models.Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    new_log = models.Sensor_Log(
        session_id=session_id,
        pressure_detected=pressure_detected,
        motion_detected=motion_detected,
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log


@app.post("/api/session/start", status_code=status.HTTP_201_CREATED, dependencies=[Depends(verify_pi)])
def start_session(user_id: int, db: Annotated[Session, Depends(get_db)]):
    new_session = models.Session(
        user_id=user_id,
        start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="active",
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session

# only the Pi can end sessions
@app.post("/api/session/end/{session_id}", dependencies=[Depends(verify_pi)])
def end_session(session_id: int, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Session).where(models.Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    session.status = "completed"
    db.commit()
    db.refresh(session)
    return session



def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = exception.detail if exception.detail else "An error occurred. Please check your request and try again"
    if request.url.path.startswith("/api"):
        return JSONResponse(status_code=exception.status_code, content={"detail": message})
    return templates.TemplateResponse(
        request,
        "error.html",
        {"status_code": exception.status_code, "title": exception.status_code, "message": message},
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )
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
