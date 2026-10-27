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

class AdminCreditRequest(BaseModel):
    admin_email: str
    target_email: str
    amount: int

@app.get("/")
def read_root():
    return {"status": "online", "message": "Luxo Tool Pro API is running"}

@app.post("/register")
def register(user_data: UserAuth):
    email_clean = user_data.email.strip().lower()
    db: Session = SessionLocal()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    
    # Asignación automática de administrador para tu correo principal
    is_admin_val = 1 if email_clean == "canelope21@hotmail.com" or "admin" in email_clean else 0
    new_user = User(
        email=email_clean, 
        password=user_data.password.strip(), 
        credits=5, 
        is_admin=is_admin_val
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    db.close()
    return {"success": True, "message": "Usuario registrado con éxito", "credits": new_user.credits}

@app.post("/login")
def login(user_data: UserAuth):
    email_clean = user_data.email.strip().lower()
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == email_clean, User.password == user_data.password.strip()).first()
    db.close()
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    return {
        "success": True, 
        "message": "Inicio de sesión exitoso", 
        "email": user.email, 
        "credits": user.credits,
        "is_admin": bool(user.is_admin) or user.email == "canelope21@hotmail.com"
    }

@app.post("/use-credits")
def use_credits(data: CreditUsageRequest):
    email_clean = data.email.strip().lower()
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == email_clean).first()
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

# ENDPOINT EXCLUSIVO DE ADMIN: Recarga manual segura de créditos
@app.post("/admin/add-credits")
def admin_add_credits(data: AdminCreditRequest):
    admin_clean = data.admin_email.strip().lower()
    target_clean = data.target_email.strip().lower()
    
    db: Session = SessionLocal()
    admin_user = db.query(User).filter(User.email == admin_clean, User.is_admin == 1).first()
    if not admin_user and admin_clean != "canelope21@hotmail.com":
        db.close()
        raise HTTPException(status_code=403, detail="Acceso denegado: No eres administrador")
    
    target_user = db.query(User).filter(User.email == target_clean).first()
    if not target_user:
        db.close()
        raise HTTPException(status_code=404, detail="El usuario a recargar no existe")
    
    target_user.credits += data.amount
    db.commit()
    db.refresh(target_user)
    new_balance = target_user.credits
    db.close()
    
    return {"success": True, "new_balance": new_balance}