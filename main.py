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

# =========================================================================
# 🎛️ CONTROL CENTRAL DE SERVICIOS, PRECIOS Y ESTADOS (ONLINE / OFFLINE)
# Modifica, agrega o apaga servicios aquí directamente sin compilar nada.
# =========================================================================
SERVICES_CATALOG = {
    "Bypass A12+": {
        "cost": 8,
        "online": True,
        "description": "Bypass A12+ autorizado mediante comprobante"
    },
    "UNLOCK BOOTLOADER (INFINIX / ITEL / TECNO)": {
        "cost": 6,
        "online": True,
        "description": "Desbloqueo oficial de bootloader por créditos"
    },
    "MI ASSISTANT FRP (XIAOMI) [ONLINE]": {
        "cost": 6,
        "online": True,
        "description": "Servicio gestionado mediante conexión remota segura"
    },
    "SAMSUNG KG BYPASS [ONLINE]": {
        "cost": 10,
        "online": True,
        "description": "Servicio gestionado mediante conexión remota segura"
    },
    "UNLOCKTOOL (RENTA 6 HORAS)": {
        "cost": 4,
        "online": True,
        "description": "Acceso remoto a Unlocktool por 6 hrs"
    },
    "TSM TOOL PRO (RENTA 6 HORAS)": {
        "cost": 4,
        "online": True,
        "description": "Acceso remoto a TSM Tool por 6 hrs"
    },
    "DFT PRO (RENTA 6 HORAS)": {
        "cost": 5,
        "online": True,
        "description": "Acceso remoto a DFT Pro por 6 hrs"
    }
}

DEFAULT_COST = 1

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
    service_name: str

class AdminCreditRequest(BaseModel):
    admin_email: str
    target_email: str
    amount: int

@app.get("/")
def read_root():
    return {"status": "online", "message": "Luxo Tool Pro API is running"}

@app.get("/services")
def get_services():
    """Devuelve el catálogo completo de servicios, precios y estado (Online/Offline) para la app"""
    return SERVICES_CATALOG

@app.post("/register")
def register(user_data: UserAuth):
    email_clean = user_data.email.strip().lower()
    db: Session = SessionLocal()
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    
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
    
    # Verificar si el servicio existe en el catálogo del servidor
    service_info = SERVICES_CATALOG.get(data.service_name)
    if not service_info:
        raise HTTPException(status_code=400, detail="El servicio solicitado no existe.")
    
    # Validar si el servicio está activo (Online)
    if not service_info.get("online", True):
        raise HTTPException(status_code=400, detail="Lo sentimos, este servicio se encuentra OFFLINE temporalmente.")
    
    cost = service_info.get("cost", DEFAULT_COST)
    
    db: Session = SessionLocal()
    user = db.query(User).filter(User.email == email_clean).first()
    if not user:
        db.close()
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    if user.credits < cost:
        db.close()
        raise HTTPException(status_code=400, detail=f"Créditos insuficientes. Este servicio requiere {cost} créditos.")
    
    user.credits -= cost
    db.commit()
    db.refresh(user)
    remaining = user.credits
    db.close()
    return {"success": True, "remaining_credits": remaining, "cost_charged": cost}

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