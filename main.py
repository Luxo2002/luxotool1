from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Inicialización de FastAPI para Render
app = FastAPI(title="Luxo Tool Pro Cloud Backend")

# Configuración de Base de Datos SQLite en Render
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Modelo de Usuario en Base de Datos
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    credits = Column(Integer, default=5)
    is_admin = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# Esquemas de Petición Pydantic
class UserAuth(BaseModel):
    email: str
    password: str

class CreditUsageRequest(BaseModel):
    email: str
    cost: int = 1

@app.get("/")
def read_root():
    return {"status": "online", "message": "Luxo Tool Pro API is running"}

@app.post("/register")
def register(user_data: UserAuth):
    db: Session = SessionLocal()
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    
    new_user = User(email=user_data.email, password=user_data.password, credits=5)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    return {"success": True, "message": "Usuario registrado con éxito", "credits": new_user.credits}

@app.post("/login")
def login(user_data: UserAuth):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == user_data.email, User.password == user_data.password).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    return {
        "success": True, 
        "message": "Inicio de sesión exitoso", 
        "email": user.email, 
        "credits": user.credits,
        "is_admin": bool(user.is_admin)
    }

# Endpoint para descontar créditos (Soporta /use-credits que llama el cliente)
@app.post("/use-credits")
def use_credits(data: CreditUsageRequest):
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == data.email).first()
    
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    if user.credits < data.cost:
        db.close()
        raise HTTPException(status_code=400, detail="Créditos insuficientes")
    
    user.credits -= data.cost
    db.commit()
    db.refresh(user)
    remaining = user.credits
    db.close()
    
    return {"success": True, "remaining_credits": remaining}