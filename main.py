import os
import hmac
import hashlib
import time
import base64
import requests
from fastapi import FastAPI, HTTPException, Header, Depends
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

# Inicialización de FastAPI para Render
app = FastAPI(title="Luxo Tool Pro Cloud Backend")

# =========================================================================
# 🔐 SEGURIDAD: CLAVE SECRETA PARA FIRMAR TOKENS DE SESIÓN
# Defínela como variable de entorno SECRET_KEY en Render. Si no existe,
# usa un valor por defecto SOLO para que no truene (cámbialo en producción).
# =========================================================================
SECRET_KEY = os.getenv("SECRET_KEY", "cambia-esta-clave-en-render-env-vars")

# Token de Telegram: AHORA SOLO VIVE AQUÍ, EN EL SERVIDOR. Ya no va dentro
# del .exe que se distribuye, así nadie puede extraerlo del cliente.
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8966225068:AAFwTooudiSuJY3b6Eztof_ftaAm5htb8E4")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "8236514362")


def enviar_alerta_telegram(mensaje: str):
    if not TELEGRAM_BOT_TOKEN or not ADMIN_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": ADMIN_CHAT_ID, "text": mensaje, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"Error enviando alerta a Telegram: {e}")


def crear_token(email: str, is_admin: bool, horas_validez: int = 12) -> str:
    """Crea un token firmado (email.expiración.firma). No requiere guardar nada en base de datos."""
    expira = int(time.time()) + horas_validez * 3600
    payload = f"{email}:{int(is_admin)}:{expira}"
    firma = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
    token_crudo = f"{payload}:{firma}"
    return base64.urlsafe_b64encode(token_crudo.encode()).decode()


def verificar_token(token: str):
    """Devuelve (email, is_admin) si el token es válido, o lanza 401 si no."""
    try:
        decodificado = base64.urlsafe_b64decode(token.encode()).decode()
        email, is_admin_str, expira_str, firma = decodificado.split(":")
        payload = f"{email}:{is_admin_str}:{expira_str}"
        firma_esperada = hmac.new(SECRET_KEY.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(firma, firma_esperada):
            raise ValueError("Firma inválida")
        if int(expira_str) < int(time.time()):
            raise ValueError("Token expirado")
        return email, bool(int(is_admin_str))
    except Exception:
        raise HTTPException(status_code=401, detail="Sesión inválida o expirada. Vuelve a iniciar sesión.")


def requerir_usuario(authorization: str = Header(default=None)) -> str:
    """Dependencia de FastAPI: exige un token válido de CUALQUIER usuario logueado
    (a diferencia de requerir_admin, no necesita ser administrador). Devuelve su email."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Debes iniciar sesión de nuevo.")
    token = authorization.split(" ", 1)[1]
    email, _ = verificar_token(token)
    return email


def requerir_admin(authorization: str = Header(default=None)):
    """Dependencia de FastAPI: exige un token válido de un usuario admin en el header Authorization."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el token de sesión (header Authorization).")
    token = authorization.split(" ", 1)[1]
    email, is_admin = verificar_token(token)
    if not is_admin:
        raise HTTPException(status_code=403, detail="Acceso denegado: no eres administrador.")
    return email

# Configuración de Base de Datos SQLite en Render
DATABASE_URL = "sqlite:///./users.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# =========================================================================
# 🎛️ CONTROL CENTRAL DE PRECIOS Y ESTADOS (ONLINE / OFFLINE)
# =========================================================================
SERVICES_CATALOG = {
    "Bypass A12+": {
        "cost": 8,
        "online": True,
        "description": "Bypass A12+ autorizado mediante comprobante"
    },
    "FRP KEY": {
        "cost": 10,
        "online": True,
        "description": "Desbloqueo rápido mediante FRP Key"
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
    credits = Column(Integer, default=0)
    is_admin = Column(Integer, default=0)

Base.metadata.create_all(bind=engine)

# Esquemas de Petición Pydantic (Obligatorios para que FastAPI acepte los datos)
class UserAuth(BaseModel):
    email: str
    password: str

class CreditUsageRequest(BaseModel):
    service_name: str

class AdminCreditRequest(BaseModel):
    target_email: str
    amount: int


class PaymentNotifyRequest(BaseModel):
    email: str
    amount: str
    binance_id: str

@app.get("/")
def read_root():
    return {"status": "online", "message": "Luxo Tool Pro API is running"}

@app.get("/services")
def get_services():
    return SERVICES_CATALOG

@app.post("/register")
def register(user_data: UserAuth):
    email_clean = user_data.email.strip().lower()
    db: Session = SessionLocal()
    
    existing_user = db.query(User).filter(User.email == email_clean).first()
    if existing_user:
        db.close()
        raise HTTPException(status_code=400, detail="El correo ya está registrado.")
    
    # 🔒 Antes: cualquiera que pusiera "admin" en su correo se volvía admin. Corregido.
    is_admin_val = 1 if email_clean == "canelope21@hotmail.com" else 0
    
    new_user = User(
        email=email_clean, 
        password=user_data.password.strip(), 
        credits=0,  # Nuevos usuarios inician con 0 créditos
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
    
    if not user:
        db.close()
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")
    
    if email_clean == "canelope21@hotmail.com" and not user.is_admin:
        user.is_admin = 1
        db.commit()

    is_admin_final = bool(user.is_admin) or user.email == "canelope21@hotmail.com"
    token = crear_token(user.email, is_admin_final)

    user_info = {
        "success": True, 
        "message": "Inicio de sesión exitoso", 
        "email": user.email, 
        "credits": user.credits,
        "is_admin": is_admin_final,
        "token": token
    }
    db.close()
    return user_info

@app.post("/use-credits")
def use_credits(data: CreditUsageRequest, email_clean: str = Depends(requerir_usuario)):
    # 🔒 email_clean ahora viene del TOKEN verificado, no de lo que mande el cliente.
    # Ya nadie puede descontarle créditos a otro usuario solo sabiendo su correo.
    service_info = SERVICES_CATALOG.get(data.service_name)
    if not service_info:
        raise HTTPException(status_code=400, detail=f"El servicio '{data.service_name}' no existe.")
    
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

@app.post("/notify-payment")
def notify_payment(data: PaymentNotifyRequest):
    """El cliente llama aquí en vez de hablarle directo a Telegram.
    Así el TELEGRAM_BOT_TOKEN nunca sale del servidor."""
    mensaje = f"💳 *AVISO DE PAGO*\nCorreo: {data.email}\nCantidad: {data.amount}\nBinance ID: {data.binance_id}"
    enviar_alerta_telegram(mensaje)
    return {"success": True}


@app.post("/admin/add-credits")
def admin_add_credits(data: AdminCreditRequest, admin_email: str = Depends(requerir_admin)):
    # admin_email ahora viene del TOKEN verificado por el servidor, no de lo que mande el cliente.
    # Ya no se puede falsificar enviando cualquier correo en el body.
    target_clean = data.target_email.strip().lower()

    db: Session = SessionLocal()
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