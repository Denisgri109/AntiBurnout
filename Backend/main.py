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

Base.metadata.create_all(bind=engine)

app = FastAPI()

# app.mount("/media", StaticFiles(directory="media"), name="media")

app.mount("/static", StaticFiles(directory="../Frontend"), name="static")
templates = Jinja2Templates(directory="../Frontend")



@app.get("/",  include_in_schema=False, name="home")
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"title": "Home"})


@app.get("/Login",  include_in_schema=False, name="login")
def login_page(request: Request):
    return templates.TemplateResponse(request, "Login.html", {"title": "Login"})



@app.get("/Register",  include_in_schema=False, name="register")
def register_page(request: Request):
    return templates.TemplateResponse(request, "Register.html", {"title": "Register"})


@app.get("/Dashboard", include_in_schema=False)
def dashboard_page(request:Request, user_id:int, db: Annotated[Session, Depends(get_db)]):
    result = db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = db.execute(select(models.Session).where(models.Session.user_id == user_id))
    sessions = result.scalars().all()


    return templates.TemplateResponse( request, "Dashboard.html", {"user": user,"sessions": sessions, "title": "User Dashboard"})



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
    new_user = models.User(username=username,email=email,password_hash=password)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user

@app.post("/Login", include_in_schema=False)
def login_user(request: Request,db: Annotated[Session, Depends(get_db)],email: str = Form(...),password: str = Form(...)): 
    result = db.execute(select(models.User).where(models.User.email == email))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if user.password_hash != password:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid password")
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
