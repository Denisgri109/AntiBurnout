from fastapi import FastAPI, Request, HTTPException, status, Depends, Form
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from Database.schemas import UserCreate, UserResponse
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.orm import Session
from Database import models
from Database.database import Base, engine, get_db
from datetime import datetime
from pathlib import Path
import bcrypt


Base.metadata.create_all(bind=engine)

app = FastAPI()

# app.mount("/media", StaticFiles(directory="media"), name="media")

FRONTEND_DIRECTORY = Path(__file__).resolve().parent.parent / "Frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIRECTORY), name="static")
templates = Jinja2Templates(directory=FRONTEND_DIRECTORY)



@app.get("/",  include_in_schema=False, name="home")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"title": "Home"})


@app.get("/Login",  include_in_schema=False, name="login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "Login.html", {"title": "Login"})



@app.get("/Register",  include_in_schema=False, name="register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "Register.html", {"title": "Register"})


@app.get("/Dashboard", include_in_schema=False, name="dashboard")
def dashboard_page(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user_id: int | None = None,
):
    user = None
    sessions = []
    if user_id is not None:
        result = db.execute(select(models.User).where(models.User.id == user_id))
        user = result.scalars().first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        result = db.execute(select(models.Session).where(models.Session.user_id == user_id))
        sessions = result.scalars().all()

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"user": user, "sessions": sessions, "title": "User Dashboard"},
    )


@app.get("/Contact", include_in_schema=False, name="contact")
def contact_page(request: Request):
    return templates.TemplateResponse(request, "ContactUs.html", {"title": "Contact"})



@app.post("/api/user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.username == user.username))
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists")
    result = db.execute(select(models.User).where(models.User.email == user.email))
    existing_email = result.scalars().first()
    if existing_email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    new_user = models.User(username = user.username,email = user.email,password_hash = user.password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user 


@app.get("/api/user/{user_id}", response_model = UserResponse)
def get_user(user_id: int, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if user:
        return user
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")



@app.post("/Register", include_in_schema=False)
def register_user(request: Request,db: Annotated[Session, Depends(get_db)],username: str = Form(...),email: str = Form(...),password: str = Form(...),passwordConfirmation: str = Form(...)):

    if password != passwordConfirmation:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password doesn't match")

    hashed_password = get_password_hash(password)

    new_user = models.User(username=username,email=email,password_hash=hashed_password)


    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return templates.TemplateResponse(request, "Dashboard.html", {"new_user": new_user, "title": "User Dashboard"})

@app.post("/Login", include_in_schema=False)
def login_user(request: Request,db: Annotated[Session, Depends(get_db)],email: str = Form(...),password: str = Form(...)): 
    result = db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
        )
    
    is_valid = verify_password(password, user.password_hash)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Wrong email or password",
        )

    return templates.TemplateResponse(request, "Dashboard.html", {"user": user, "title": "User Dashboard"})




@app.post("/api/sensor_log", status_code=status.HTTP_201_CREATED)
def create_sensor_log(session_id: int, pressure_detected: int, motion_detected:int,  db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.Session).where(models.Session.id == session_id))
    session = result.scalars().first()
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")


    new_log = models.Sensor_Log(session_id=session_id, pressure_detected=pressure_detected, motion_detected=motion_detected)

    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    return new_log 

# Start a session when user sits down


@app.post("/api/session/start", status_code=status.HTTP_201_CREATED)
def start_session(user_id: int, db: Annotated[Session, Depends(get_db)]):
    new_session = models.Session(
        user_id=user_id,
        start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        status="active"
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


# End session when user finishes or takes break



@app.post("/api/session/end/{session_id}")
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



@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request:Request, exception:StarletteHTTPException):
    message = (
    exception.detail
        if exception.detail
        else "An error occurred. Please check your request and try again"
    )
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code = exception.status_code,
            content = {"detail": message}
        )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
        "status_code": exception.status_code,
         "title": exception.status_code,
         "message":exception.detail,
         },
        status_code = exception.status_code,
    )




def get_password_hash(password: str) -> str:
    """Hashes a plain text password with a randomly generated salt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed_password_bytes = bcrypt.hashpw(password_bytes, salt)
    
    return hashed_password_bytes.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain text password against a stored hash."""
    plain_password_bytes = plain_password.encode('utf-8')
    hashed_password_bytes = hashed_password.encode('utf-8')
    
    return bcrypt.checkpw(plain_password_bytes, hashed_password_bytes)


    
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request:Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
            return JSONResponse(
                status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
                content = {"detail": exception.errors()}
            )
    return templates.TemplateResponse(
        request,
        "error.html",
        {
        "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message":"Invalid request. Please check your input and try again",
            },
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT,
    )
