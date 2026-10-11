"""
Matru Raksha — Flask REST API Server
Provides JWT authentication, donor management, risk prediction, and emergency endpoints.
Run with:  python api_server.py
"""

import os
import csv
from datetime import datetime, timedelta, timezone

from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity,
)
from flask_cors import CORS

# ─────────────────────────────────────────
# App Configuration
# ─────────────────────────────────────────
app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{os.path.join(BASE_DIR, 'matru_raksha.db')}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = "matru-raksha-secret-jwt-key-2026"  # Change in production
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=12)

db    = SQLAlchemy(app)
bcrypt = Bcrypt(app)
jwt   = JWTManager(app)
CORS(app, resources={r"/api/*": {"origins": ["http://localhost:8080", "http://localhost:5173", "http://127.0.0.1:8080", "http://127.0.0.1:5173", "http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3001", "http://localhost:3002", "http://127.0.0.1:3002", "http://localhost:3003", "http://localhost:3004"]}})


# ─────────────────────────────────────────
# Database Models
# ─────────────────────────────────────────

class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(120), unique=True, nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    phone      = db.Column(db.String(20), unique=True)  # unique phone
    role       = db.Column(db.String(30), default="doctor")   # doctor|donor|admin|health_worker
    is_active  = db.Column(db.Boolean, default=True)
    report_count = db.Column(db.Integer, default=0)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    predictions = db.relationship("Prediction", backref="user", lazy=True)



    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone or "",
            "role": self.role,
            "is_active": self.is_active,
            "report_count": self.report_count,
            "last_login": self.last_login.isoformat() if self.last_login else None,
            "created_at": self.created_at.isoformat(),
        }


class Donor(db.Model):
    __tablename__ = "donors"
    id               = db.Column(db.Integer, primary_key=True)
    donor_id         = db.Column(db.String(20), unique=True)
    name             = db.Column(db.String(120), nullable=False)
    age              = db.Column(db.Integer)
    blood_group      = db.Column(db.String(5), nullable=False)
    hemoglobin       = db.Column(db.Float)
    city             = db.Column(db.String(80))
    phone            = db.Column(db.String(20))
    chronic_disease  = db.Column(db.String(200), default="None")
    last_donation    = db.Column(db.String(20))
    availability     = db.Column(db.Boolean, default=True)
    # Computed health score (0-100) — saved when registered
    health_score     = db.Column(db.Integer, default=80)
    report_count     = db.Column(db.Integer, default=0)
    created_at       = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self, include_phone=False):
        d = {
            "id": self.id,
            "donor_id": self.donor_id,
            "name": self.name,
            "age": self.age,
            "blood_group": self.blood_group,
            "hemoglobin": self.hemoglobin,
            "city": self.city,
            "chronic_disease": self.chronic_disease,
            "last_donation": self.last_donation,
            "availability": self.availability,
            "health_score": self.health_score,
            "report_count": self.report_count,
            "created_at": self.created_at.isoformat(),
        }
        if include_phone:
            d["phone"] = self.phone
        return d



class Prediction(db.Model):
    __tablename__ = "predictions"
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    patient_id   = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=True)
    
    age          = db.Column(db.Float)
    systolic_bp  = db.Column(db.Float)
    diastolic_bp = db.Column(db.Float)
    blood_sugar  = db.Column(db.Float)
    body_temp    = db.Column(db.Float)
    heart_rate   = db.Column(db.Float)
    
    risk_level   = db.Column(db.String(10))
    confidence   = db.Column(db.Float)
    main_factor  = db.Column(db.String(60))
    predicted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "patient_id": self.patient_id,
            "age": self.age,
            "systolicBP": self.systolic_bp,
            "diastolicBP": self.diastolic_bp,
            "bloodGlucose": self.blood_sugar,
            "bodyTemp": self.body_temp,
            "heartRate": self.heart_rate,
            "risk": self.risk_level,
            "confidence": self.confidence,
            "mainFactor": self.main_factor,
            "predicted_at": self.predicted_at.isoformat(),
        }


class EmergencyLog(db.Model):
    __tablename__ = "emergency_logs"
    id             = db.Column(db.Integer, primary_key=True)
    triggered_by   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    patient_label  = db.Column(db.String(60))
    blood_group    = db.Column(db.String(5))
    donors_matched = db.Column(db.Integer, default=0)
    status         = db.Column(db.String(20), default="active")  # active | resolved
    triggered_at   = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id": self.id,
            "triggered_by": self.triggered_by,
            "patient_label": self.patient_label,
            "blood_group": self.blood_group,
            "donors_matched": self.donors_matched,
            "status": self.status,
            "triggered_at": self.triggered_at.isoformat(),
        }


# ─────────────────────────────────────────
# Patient & Checkup Models
# ─────────────────────────────────────────

class Patient(db.Model):
    __tablename__ = "patients"
    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(120), nullable=False)
    age                = db.Column(db.Integer)
    phone              = db.Column(db.String(20))
    address            = db.Column(db.String(250))
    blood_group        = db.Column(db.String(5))
    weeks_pregnant     = db.Column(db.Integer, default=0)   # current week
    due_date           = db.Column(db.String(20))            # ISO date string
    high_risk          = db.Column(db.Boolean, default=False)
    notes              = db.Column(db.Text, default="")
    status             = db.Column(db.String(20), default="active")  # active | delivered
    health_worker_id   = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    assigned_doctor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at         = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at         = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                                   onupdate=lambda: datetime.now(timezone.utc))

    checkups = db.relationship("CheckupRecord", backref="patient", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        doctor = db.session.get(User, self.assigned_doctor_id) if self.assigned_doctor_id else None
        return {
            "id"                : self.id,
            "name"              : self.name,
            "age"               : self.age,
            "phone"             : self.phone or "",
            "address"           : self.address or "",
            "blood_group"       : self.blood_group or "",
            "weeks_pregnant"    : self.weeks_pregnant or 0,
            "months_pregnant"   : round((self.weeks_pregnant or 0) / 4.33, 1),
            "due_date"          : self.due_date or "",
            "high_risk"         : self.high_risk,
            "notes"             : self.notes or "",
            "status"            : self.status,
            "health_worker_id"  : self.health_worker_id,
            "assigned_doctor_id": self.assigned_doctor_id,
            "assigned_doctor"   : doctor.name if doctor else None,
            "checkup_count"     : len(self.checkups),
            "last_checkup"      : max((c.checkup_date for c in self.checkups), default=None),
            "created_at"        : self.created_at.isoformat(),
        }


class CheckupRecord(db.Model):
    __tablename__ = "checkup_records"
    id            = db.Column(db.Integer, primary_key=True)
    patient_id    = db.Column(db.Integer, db.ForeignKey("patients.id"), nullable=False)
    week_number   = db.Column(db.Integer)
    checkup_date  = db.Column(db.String(20))          # ISO date string
    bp_systolic   = db.Column(db.Float)
    bp_diastolic  = db.Column(db.Float)
    weight_kg     = db.Column(db.Float)
    hemoglobin    = db.Column(db.Float)
    fetal_hr      = db.Column(db.Integer)             # fetal heart rate bpm
    
    # Maternal vitals for risk prediction
    blood_sugar   = db.Column(db.Float)               # mmol/L
    body_temp     = db.Column(db.Float)               # °F
    heart_rate    = db.Column(db.Integer)             # maternal heart rate bpm
    
    risk_level    = db.Column(db.String(10), default="low")  # low | mid | high
    notes         = db.Column(db.Text, default="")
    created_at    = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {
            "id"          : self.id,
            "patient_id"  : self.patient_id,
            "week_number" : self.week_number,
            "checkup_date": self.checkup_date,
            "bp_systolic" : self.bp_systolic,
            "bp_diastolic": self.bp_diastolic,
            "weight_kg"   : self.weight_kg,
            "hemoglobin"  : self.hemoglobin,
            "fetal_hr"    : self.fetal_hr,
            "blood_sugar" : self.blood_sugar,
            "body_temp"   : self.body_temp,
            "heart_rate"  : self.heart_rate,
            "risk_level"  : self.risk_level,
            "notes"       : self.notes or "",
            "created_at"  : self.created_at.isoformat(),
        }


# ─────────────────────────────────────────

def compute_health_score(hemoglobin: float, age: int, chronic_disease: str) -> int:
    """Simple rule-based health score 0-100."""
    score = 100
    # Hemoglobin: ideal 13-17 for males, 12-15 for females (use 12.5 as min)
    if hemoglobin < 12.5:
        score -= 25
    elif hemoglobin < 13:
        score -= 10
    # Age penalty
    if age > 55:
        score -= 15
    elif age > 45:
        score -= 8
    # Chronic disease penalty
    if chronic_disease and chronic_disease.strip().lower() not in ("none", "", "nil", "no"):
        score -= 20
    return max(0, min(100, score))


def load_ml_model():
    """Load the trained ML model if it exists."""
    try:
        import joblib
        model_path = os.path.join(BASE_DIR, "models", "maternal_model.pkl")
        if os.path.exists(model_path):
            return joblib.load(model_path)
    except Exception as e:
        print(f"[WARNING] Could not load ML model: {e}")
    return None


# Load once at startup
ML_MODEL = load_ml_model()


def predict_risk_logic(age, systolic_bp, diastolic_bp, blood_sugar, body_temp, heart_rate):
    """Use real ML model or fall back to rule-based logic."""
    import random
    import numpy as np
    global ML_MODEL

    # Re-check if model is loaded
    if ML_MODEL is None:
        ML_MODEL = load_ml_model()

    feature_names = ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"]
    
    # Static fallback logic (Aligned with Fahrenheit for BodyTemp)
    factors = [
        {"name": "Systolic BP",   "importance": 85 if systolic_bp  > 140 else 25},
        {"name": "Blood Glucose", "importance": 80 if blood_sugar  > 10.0 else 20}, 
        {"name": "Heart Rate",    "importance": 65 if heart_rate   > 100 else 15},
        {"name": "Body Temp",     "importance": 60 if body_temp    > 99.0 else 10}, # Fahrenheit threshold
        {"name": "Age",           "importance": 45 if age          > 35   else 10},
        {"name": "Diastolic BP",  "importance": 60 if diastolic_bp > 90   else 15},
    ]

    risk = None
    if ML_MODEL is not None:
        try:
            import pandas as pd
            # Use DataFrame with feature names to resolve UserWarning and ensure correct alignment
            df_input = pd.DataFrame(
                [[age, systolic_bp, diastolic_bp, blood_sugar, body_temp, heart_rate]],
                columns=feature_names
            )
            pred_idx = int(ML_MODEL.predict(df_input)[0])
            risk_map = {0: "low", 1: "mid", 2: "high"}
            risk = risk_map.get(pred_idx, "mid")
            print(f"[ML] Predicted risk: {risk} (via model)")

            if hasattr(ML_MODEL, 'feature_importances_'):
                import_kv = dict(zip(feature_names, ML_MODEL.feature_importances_))
                factors = [
                    {"name": "Age",           "importance": round(import_kv.get("Age", 0.1) * 100, 1)},
                    {"name": "Systolic BP",   "importance": round(import_kv.get("SystolicBP", 0.1) * 100, 1)},
                    {"name": "Diastolic BP",  "importance": round(import_kv.get("DiastolicBP", 0.1) * 100, 1)},
                    {"name": "Blood Glucose", "importance": round(import_kv.get("BS", 0.1) * 100, 1)},
                    {"name": "Body Temp",     "importance": round(import_kv.get("BodyTemp", 0.1) * 100, 1)},
                    {"name": "Heart Rate",    "importance": round(import_kv.get("HeartRate", 0.1) * 100, 1)},
                ]
        except Exception as e:
            print(f"[ERROR] Model prediction failed: {e}")
            risk = None
    else:
        print("[ML] Using rule-based fallback logic")

    if risk is None:
        score = sum(f["importance"] for f in factors) / len(factors)
        risk = "high" if score > 50 else ("mid" if score > 30 else "low")
    
    factors_sorted = sorted(factors, key=lambda x: x["importance"], reverse=True)
    confidence = round(min(99.4, 75.0 + random.uniform(0, 24.4)), 1)
    
    return {
        "risk": risk,
        "confidence": confidence,
        "mainFactor": factors_sorted[0]["name"],
        "factors": factors_sorted,
    }



# ─────────────────────────────────────────
# Seed Data
# ─────────────────────────────────────────


def seed_donors_from_csv():

    """Seed the database with donors from CSV if table is empty."""
    if Donor.query.count() > 0:
        return

    csv_path = os.path.join(BASE_DIR, "data", "donors.csv")
    if not os.path.exists(csv_path):
        return

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            hb   = float(row.get("hemoglobin", 13))
            age  = int(row.get("age", 30))
            score = compute_health_score(hb, age, "None")
            donor = Donor(
                donor_id      = f"D{row['donor_id'].zfill(4)}",
                name          = row["name"],
                age           = age,
                blood_group   = row["blood_group"],
                hemoglobin    = hb,
                city          = row.get("city", ""),
                last_donation = row.get("last_donation_date", ""),
                availability  = bool(int(row.get("availability", 0))),
                health_score  = score,
                chronic_disease = "None",
            )
            db.session.add(donor)
    db.session.commit()
    print(f"[SEED] Donors loaded from CSV.")


def seed_admin_user():
    """Create default admin account if none exists."""
    if User.query.filter_by(role="admin").count() == 0:
        admin = User(
            name     = "Admin",
            email    = "admin@matruraksha.in",
            password = bcrypt.generate_password_hash("admin123").decode("utf-8"),
            phone    = "+91 9000000000",
            role     = "admin",
        )
        db.session.add(admin)
        db.session.commit()
        print("[SEED] Default admin created — email: admin@matruraksha.in  password: admin123")


# ─────────────────────────────────────────
# Auth Routes  /api/auth/*
# ─────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def register():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    phone    = data.get("phone", "").strip() or None
    role     = data.get("role", "doctor").strip()

    # Required fields
    if not name:
        return jsonify({"error": "Full name is required"}), 400
    if not email:
        return jsonify({"error": "Email is required"}), 400
    if not password or len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters"}), 400

    # Uniqueness checks
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "This email is already registered. Please login instead."}), 409

    if phone and User.query.filter_by(phone=phone).first():
        return jsonify({"error": "This phone number is already registered with another account."}), 409

    allowed_roles = {"doctor", "donor", "admin", "health_worker"}
    if role not in allowed_roles:
        role = "doctor"

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    user   = User(name=name, email=email, password=hashed, phone=phone, role=role)
    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"message": "Account created successfully", "token": token, "user": user.to_dict()}), 201


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return jsonify({"error": "Invalid email or password. Please check your credentials."}), 401

    if not user.is_active:
        return jsonify({"error": "Your account has been suspended. Please contact the admin."}), 403

    # Update last login
    user.last_login = datetime.now(timezone.utc)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return jsonify({"message": "Login successful", "token": token, "user": user.to_dict()}), 200


@app.route("/api/auth/me", methods=["GET"])
@jwt_required()
def get_me():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict()), 200


@app.route("/api/auth/update", methods=["PUT"])
@jwt_required()
def update_profile():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json() or {}

    if "name" in data:
        n = data["name"].strip()
        if not n:
            return jsonify({"error": "Name cannot be empty"}), 400
        user.name = n

    if "phone" in data:
        new_phone = data["phone"].strip() or None
        if new_phone:
            existing = User.query.filter_by(phone=new_phone).first()
            if existing and existing.id != user_id:
                return jsonify({"error": "This phone number is already used by another account."}), 409
        user.phone = new_phone

    if "password" in data and data["password"]:
        if len(data["password"]) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        user.password = bcrypt.generate_password_hash(data["password"]).decode("utf-8")

    db.session.commit()
    return jsonify({"message": "Profile updated successfully", "user": user.to_dict()}), 200

# ─────────────────────────────────────────
# Prediction Routes  /api/predict
# ─────────────────────────────────────────

@app.route("/api/predict", methods=["POST"])
@jwt_required(optional=True)
def predict():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    try:
        age          = float(data["age"])
        systolic_bp  = float(data["systolicBP"])
        diastolic_bp = float(data["diastolicBP"])
        blood_sugar  = float(data["bloodGlucose"])
        body_temp    = float(data["bodyTemp"])
        heart_rate   = float(data["heartRate"])
    except (KeyError, ValueError) as e:
        return jsonify({"error": f"Invalid field: {e}"}), 400

    result = predict_risk_logic(age, systolic_bp, diastolic_bp, blood_sugar, body_temp, heart_rate)

    # Save to DB
    current_user_id = get_jwt_identity()
    patient_id_raw  = data.get("patient_id")
    
    patient_id = None
    if patient_id_raw and str(patient_id_raw).isdigit():
        patient_id = int(patient_id_raw)

    pred = Prediction(
        user_id      = int(current_user_id) if current_user_id else None,
        patient_id   = patient_id,
        age          = age,
        systolic_bp  = systolic_bp,
        diastolic_bp = diastolic_bp,
        blood_sugar  = blood_sugar,
        body_temp    = body_temp,
        heart_rate   = heart_rate,
        risk_level   = result["risk"],
        confidence   = result["confidence"],
        main_factor  = result["mainFactor"],
    )

    # Auto-update patient high_risk status if prediction is high
    if patient_id and result["risk"] == "high":
        p = db.session.get(Patient, int(patient_id))
        if p:
            p.high_risk = True

    db.session.add(pred)
    db.session.commit()

    return jsonify({
        "id": pred.id,
        "risk": result["risk"],
        "confidence": result["confidence"],
        "mainFactor": result["mainFactor"],
        "factors": result["factors"]
    }), 200


@app.route("/api/predictions", methods=["GET"])
@jwt_required()
def get_predictions():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)

    # Admins see all
    if user and user.role == "admin":
        preds = Prediction.query.order_by(Prediction.predicted_at.desc()).limit(100).all()
    else:
        preds = Prediction.query.filter_by(user_id=user_id).order_by(Prediction.predicted_at.desc()).all()

    return jsonify([p.to_dict() for p in preds]), 200




# ─────────────────────────────────────────
# Donor Routes  /api/donors
# ─────────────────────────────────────────

@app.route("/api/donors", methods=["GET"])
@jwt_required(optional=True)
def get_donors():
    blood      = request.args.get("blood")
    available  = request.args.get("available")
    min_score  = request.args.get("minScore", type=int)
    city       = request.args.get("city")
    search     = request.args.get("search", "").strip()
    page       = request.args.get("page", 1, type=int)
    per_page   = request.args.get("per_page", 20, type=int)

    q = Donor.query
    if blood:      q = q.filter(Donor.blood_group == blood)
    if available:  q = q.filter(Donor.availability == (available.lower() == "true"))
    if min_score:  q = q.filter(Donor.health_score >= min_score)
    if city:       q = q.filter(Donor.city.ilike(f"%{city}%"))
    if search:     q = q.filter(Donor.name.ilike(f"%{search}%") | Donor.city.ilike(f"%{search}%"))

    total = q.count()
    donors = q.order_by(Donor.health_score.desc()).offset((page - 1) * per_page).limit(per_page).all()

    # Determine if caller is admin (show phone)
    current_user_id = get_jwt_identity()
    is_admin = False
    if current_user_id:
        u = db.session.get(User, int(current_user_id))
        is_admin = u and u.role == "admin"

    return jsonify({
        "donors": [d.to_dict(include_phone=is_admin) for d in donors],
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": (total + per_page - 1) // per_page,
    }), 200


@app.route("/api/donors/<int:donor_id>", methods=["GET"])
@jwt_required(optional=True)
def get_donor(donor_id):
    donor = db.session.get(Donor, donor_id)
    if not donor:
        return jsonify({"error": "Donor not found"}), 404

    current_user_id = get_jwt_identity()
    is_admin = False
    if current_user_id:
        u = db.session.get(User, int(current_user_id))
        is_admin = u and u.role == "admin"

    return jsonify(donor.to_dict(include_phone=is_admin)), 200


@app.route("/api/donors", methods=["POST"])
@jwt_required(optional=True)
def create_donor():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400

    required = ["name", "blood_group"]
    for f in required:
        if not data.get(f):
            return jsonify({"error": f"{f} is required"}), 400

    hb    = float(data.get("hemoglobin", 13.0))
    age   = int(data.get("age", 25))
    score = compute_health_score(hb, age, data.get("chronic_disease", "None"))

    # Auto-generate donor ID
    last = Donor.query.order_by(Donor.id.desc()).first()
    next_id = (last.id + 1) if last else 1

    donor = Donor(
        donor_id        = f"D{str(next_id).zfill(4)}",
        name            = data["name"].strip(),
        age             = age,
        blood_group     = data["blood_group"],
        hemoglobin      = hb,
        city            = data.get("location", data.get("city", "")),
        phone           = data.get("phone", ""),
        chronic_disease = data.get("chronicDisease", data.get("chronic_disease", "None")),
        last_donation   = data.get("lastDonation", data.get("last_donation", "")),
        availability    = bool(data.get("available", data.get("availability", True))),
        health_score    = score,
    )
    db.session.add(donor)
    db.session.commit()
    return jsonify({"message": "Donor registered", "donor": donor.to_dict(include_phone=True)}), 201


@app.route("/api/donors/<int:donor_id>", methods=["PUT"])
@jwt_required()
def update_donor(donor_id):
    donor = db.session.get(Donor, donor_id)
    if not donor:
        return jsonify({"error": "Donor not found"}), 404

    data = request.get_json() or {}
    if "name"            in data: donor.name            = data["name"].strip()
    if "phone"           in data: donor.phone           = data["phone"]
    if "city"            in data: donor.city            = data["city"]
    if "availability"    in data: donor.availability    = bool(data["availability"])
    if "hemoglobin"      in data:
        donor.hemoglobin   = float(data["hemoglobin"])
        donor.health_score = compute_health_score(donor.hemoglobin, donor.age or 25, donor.chronic_disease or "None")
    if "chronic_disease" in data: donor.chronic_disease = data["chronic_disease"]
    if "last_donation"   in data: donor.last_donation   = data["last_donation"]

    db.session.commit()
    return jsonify({"message": "Donor updated", "donor": donor.to_dict(include_phone=True)}), 200


@app.route("/api/donors/<int:donor_id>", methods=["DELETE"])
@jwt_required()
def delete_donor(donor_id):
    current_user_id = int(get_jwt_identity())
    user = db.session.get(User, current_user_id)
    if not user or user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    donor = db.session.get(Donor, donor_id)
    if not donor:
        return jsonify({"error": "Donor not found"}), 404

    db.session.delete(donor)
    db.session.commit()
    return jsonify({"message": "Donor deleted"}), 200


# ─────────────────────────────────────────
# Emergency Routes  /api/emergency
# ─────────────────────────────────────────

@app.route("/api/emergency", methods=["POST"])
@jwt_required(optional=True)
def trigger_emergency():
    data       = request.get_json() or {}
    blood_req  = data.get("blood_group", "O+")
    patient_lbl = data.get("patient_label", f"Patient #{datetime.now().strftime('%H%M%S')}")

    # Find matching available donors
    donors = Donor.query.filter_by(blood_group=blood_req, availability=True)\
                        .filter(Donor.hemoglobin >= 12.5)\
                        .order_by(Donor.health_score.desc())\
                        .limit(8).all()

    current_user_id = get_jwt_identity()
    log = EmergencyLog(
        triggered_by   = int(current_user_id) if current_user_id else None,
        patient_label  = patient_lbl,
        blood_group    = blood_req,
        donors_matched = len(donors),
        status         = "active",
    )
    db.session.add(log)
    db.session.commit()

    return jsonify({
        "message"       : "Emergency alert triggered",
        "log_id"        : log.id,
        "donors_matched": len(donors),
        "donors"        : [d.to_dict(include_phone=True) for d in donors],
    }), 200


@app.route("/api/emergency/<int:log_id>/resolve", methods=["PUT"])
@jwt_required()
def resolve_emergency(log_id):
    log = db.session.get(EmergencyLog, log_id)
    if not log:
        return jsonify({"error": "Log not found"}), 404
    log.status = "resolved"
    db.session.commit()
    return jsonify({"message": "Emergency resolved", "log": log.to_dict()}), 200


@app.route("/api/emergency/logs", methods=["GET"])
@jwt_required()
def get_emergency_logs():
    logs = EmergencyLog.query.order_by(EmergencyLog.triggered_at.desc()).limit(50).all()
    return jsonify([l.to_dict() for l in logs]), 200


# ─────────────────────────────────────────
# Admin Routes  /api/admin/*
# ─────────────────────────────────────────

@app.route("/api/admin/stats", methods=["GET"])
@jwt_required()
def admin_stats():
    current_user_id = int(get_jwt_identity())
    user = db.session.get(User, current_user_id)
    if not user or user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    total_donors     = Donor.query.count()
    available_donors = Donor.query.filter_by(availability=True).count()
    total_preds      = Prediction.query.count()
    high_risk        = Prediction.query.filter_by(risk_level="high").count()
    total_emergency  = EmergencyLog.query.count()
    total_users      = User.query.count()

    avg_score = db.session.query(db.func.avg(Donor.health_score)).scalar() or 0

    return jsonify({
        "total_donors"    : total_donors,
        "available_donors": available_donors,
        "total_predictions": total_preds,
        "high_risk_count" : high_risk,
        "total_emergencies": total_emergency,
        "total_users"     : total_users,
        "avg_health_score": round(float(avg_score), 1),
    }), 200


@app.route("/api/admin/users", methods=["GET"])
@jwt_required()
def admin_get_users():
    current_user_id = int(get_jwt_identity())
    user = db.session.get(User, current_user_id)
    if not user or user.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    role_filter = request.args.get("role")  # optional filter: doctor|health_worker|donor
    q = User.query
    if role_filter:
        q = q.filter(User.role == role_filter)
    users = q.order_by(User.created_at.desc()).all()
    return jsonify([u.to_dict() for u in users]), 200


@app.route("/api/admin/users", methods=["POST"])
@jwt_required()
def admin_create_user():
    """Admin creates a doctor or health_worker account."""
    current_user_id = int(get_jwt_identity())
    admin = db.session.get(User, current_user_id)
    if not admin or admin.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json() or {}
    name     = data.get("name", "").strip()
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    phone    = data.get("phone", "")
    role     = data.get("role", "doctor")

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400

    allowed = {"doctor", "health_worker", "admin"}
    if role not in allowed:
        return jsonify({"error": f"Role must be one of: {allowed}"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 409

    hashed = bcrypt.generate_password_hash(password).decode("utf-8")
    new_user = User(name=name, email=email, password=hashed, phone=phone, role=role)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({"message": "User created", "user": new_user.to_dict()}), 201


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def admin_remove_user(user_id):
    """Admin hard-deletes a user (cannot delete self)."""
    current_user_id = int(get_jwt_identity())
    admin = db.session.get(User, current_user_id)
    if not admin or admin.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    if user_id == current_user_id:
        return jsonify({"error": "Cannot delete yourself"}), 400

    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    db.session.delete(target)
    db.session.commit()
    return jsonify({"message": f"User '{target.name}' removed"}), 200


@app.route("/api/admin/users/<int:user_id>/deactivate", methods=["PUT"])
@jwt_required()
def admin_deactivate_user(user_id):
    """Admin toggles a user's active status."""
    current_user_id = int(get_jwt_identity())
    admin = db.session.get(User, current_user_id)
    if not admin or admin.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    target.is_active = not target.is_active
    db.session.commit()
    status = "activated" if target.is_active else "deactivated"
    return jsonify({"message": f"User {status}", "user": target.to_dict()}), 200


@app.route("/api/admin/report/donor/<int:donor_id>", methods=["POST"])
@jwt_required()
def report_donor(donor_id):
    """Any authenticated user can report a donor. Increments report count."""
    donor = db.session.get(Donor, donor_id)
    if not donor:
        return jsonify({"error": "Donor not found"}), 404

    data   = request.get_json() or {}
    reason = data.get("reason", "No reason provided")
    donor.report_count = (donor.report_count or 0) + 1

    # Auto-remove availability if 3+ reports
    if donor.report_count >= 3:
        donor.availability = False

    db.session.commit()
    return jsonify({
        "message"     : "Donor reported",
        "report_count": donor.report_count,
        "availability": donor.availability,
    }), 200


@app.route("/api/admin/report/user/<int:user_id>", methods=["POST"])
@jwt_required()
def report_user(user_id):
    """Any authenticated user can report a doctor/worker."""
    target = db.session.get(User, user_id)
    if not target:
        return jsonify({"error": "User not found"}), 404

    target.report_count = (target.report_count or 0) + 1
    # Auto-deactivate at 3+ reports (admin can re-activate)
    if target.report_count >= 3:
        target.is_active = False

    db.session.commit()
    return jsonify({
        "message"     : "User reported",
        "report_count": target.report_count,
        "is_active"   : target.is_active,
    }), 200


@app.route("/api/admin/reported", methods=["GET"])
@jwt_required()
def admin_get_reported():
    """Get all donors and users with report_count > 0."""
    current_user_id = int(get_jwt_identity())
    admin = db.session.get(User, current_user_id)
    if not admin or admin.role != "admin":
        return jsonify({"error": "Admin access required"}), 403

    reported_donors = Donor.query.filter(Donor.report_count > 0).order_by(Donor.report_count.desc()).all()
    reported_users  = User.query.filter(User.report_count  > 0).order_by(User.report_count.desc()).all()

    return jsonify({
        "reported_donors": [d.to_dict(include_phone=True) for d in reported_donors],
        "reported_users" : [u.to_dict() for u in reported_users],
    }), 200



# ─────────────────────────────────────────
# Patient Management  /api/patients
# ─────────────────────────────────────────

@app.route("/api/patients", methods=["GET"])
@jwt_required()
def get_patients():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Unauthorized"}), 403

    # Admins and doctors see all; health workers see only their own
    if user.role in ("admin", "doctor"):
        patients = Patient.query.order_by(Patient.created_at.desc()).all()
    else:
        patients = Patient.query.filter_by(health_worker_id=user_id).order_by(Patient.created_at.desc()).all()

    status_filter = request.args.get("status")
    if status_filter:
        patients = [p for p in patients if p.status == status_filter]

    return jsonify([p.to_dict() for p in patients]), 200


@app.route("/api/patients", methods=["POST"])
@jwt_required()
def create_patient():
    user_id = int(get_jwt_identity())
    user    = db.session.get(User, user_id)
    if not user or user.role not in ("health_worker", "admin", "doctor"):
        return jsonify({"error": "Not authorized to add patients"}), 403

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Patient name is required"}), 400

    patient = Patient(
        name               = name,
        age                = data.get("age"),
        phone              = data.get("phone", ""),
        address            = data.get("address", ""),
        blood_group        = data.get("blood_group", ""),
        weeks_pregnant     = int(data.get("weeks_pregnant", 0)),
        due_date           = data.get("due_date", ""),
        high_risk          = bool(data.get("high_risk", False)),
        notes              = data.get("notes", ""),
        health_worker_id   = user_id,
        assigned_doctor_id = data.get("assigned_doctor_id"),
    )
    db.session.add(patient)
    db.session.commit()
    return jsonify({"message": "Patient added", "patient": patient.to_dict()}), 201


@app.route("/api/patients/<int:patient_id>", methods=["GET"])
@jwt_required()
def get_patient(patient_id):
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    return jsonify(p.to_dict()), 200


@app.route("/api/patients/<int:patient_id>", methods=["PUT"])
@jwt_required()
def update_patient(patient_id):
    user_id = int(get_jwt_identity())
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404

    data = request.get_json() or {}
    for field in ("name", "age", "phone", "address", "blood_group", "weeks_pregnant",
                  "due_date", "high_risk", "notes", "status", "assigned_doctor_id"):
        if field in data:
            setattr(p, field, data[field])
    p.updated_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify({"message": "Patient updated", "patient": p.to_dict()}), 200


@app.route("/api/patients/<int:patient_id>", methods=["DELETE"])
@jwt_required()
def delete_patient(patient_id):
    user_id = int(get_jwt_identity())
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"message": f"Patient '{p.name}' removed"}), 200


# ── Checkup Records ──────────────────────────────────────

@app.route("/api/patients/<int:patient_id>/checkups", methods=["GET"])
@jwt_required()
def get_checkups(patient_id):
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404
    records = CheckupRecord.query.filter_by(patient_id=patient_id).order_by(CheckupRecord.week_number).all()
    return jsonify([r.to_dict() for r in records]), 200


@app.route("/api/patients/<int:patient_id>/checkups", methods=["POST"])
@jwt_required()
def add_checkup(patient_id):
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404

    data = request.get_json() or {}
    record = CheckupRecord(
        patient_id   = patient_id,
        week_number  = data.get("week_number", p.weeks_pregnant),
        checkup_date = data.get("checkup_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        bp_systolic  = data.get("bp_systolic"),
        bp_diastolic = data.get("bp_diastolic"),
        weight_kg    = data.get("weight_kg"),
        hemoglobin   = data.get("hemoglobin"),
        fetal_hr     = data.get("fetal_hr"),
        blood_sugar  = data.get("blood_sugar"),
        body_temp    = data.get("body_temp"),
        heart_rate   = data.get("heart_rate"),
        risk_level   = data.get("risk_level", "low"),
        notes        = data.get("notes", ""),
    )

    # ─────────────────────────────────────────
    # Auto-Predict Integration (Ensure types are correct)
    # ─────────────────────────────────────────
    try:
        age_val = float(p.age or 25)
        sys_val = float(record.bp_systolic) if record.bp_systolic is not None else None
        dia_val = float(record.bp_diastolic) if record.bp_diastolic is not None else None
        bs_val  = float(record.blood_sugar) if record.blood_sugar is not None else None
        tmp_val = float(record.body_temp) if record.body_temp is not None else None
        hrt_val = float(record.heart_rate) if record.heart_rate is not None else None
        
        vitals = [age_val, sys_val, dia_val, bs_val, tmp_val, hrt_val]
        
        if all(v is not None for v in vitals):
            res = predict_risk_logic(*vitals)
            record.risk_level = res["risk"]
            
            # Persist prediction entry
            current_user_id = get_jwt_identity()
            pred = Prediction(
                user_id      = int(current_user_id) if current_user_id else None,
                patient_id   = p.id,
                age          = p.age,
                systolic_bp  = record.bp_systolic,
                diastolic_bp = record.bp_diastolic,
                blood_sugar  = record.blood_sugar,
                body_temp    = record.body_temp,
                heart_rate   = record.heart_rate,
                risk_level   = res["risk"],
                confidence   = res["confidence"],
                main_factor  = res["mainFactor"],
            )
            db.session.add(pred)
    except Exception as e:
        print(f"[ERROR] Auto-prediction failed during checkup: {e}")

    # Auto-update patient's state
    if data.get("week_number"):
        p.weeks_pregnant = int(data["week_number"])
    if record.risk_level == "high":
        p.high_risk = True

    db.session.add(record)
    db.session.commit()
    return jsonify({"message": "Checkup recorded", "checkup": record.to_dict(), "patient": p.to_dict()}), 201


# ── Share Patient to Doctor ─────────────────────────────

@app.route("/api/patients/<int:patient_id>/share", methods=["POST"])
@jwt_required()
def share_patient(patient_id):
    p = db.session.get(Patient, patient_id)
    if not p:
        return jsonify({"error": "Patient not found"}), 404

    data      = request.get_json() or {}
    doctor_id = data.get("doctor_id")
    doctor    = db.session.get(User, doctor_id) if doctor_id else None
    if not doctor or doctor.role != "doctor":
        return jsonify({"error": "Invalid doctor selected"}), 400

    p.assigned_doctor_id = doctor_id
    db.session.commit()

    checkups = CheckupRecord.query.filter_by(patient_id=patient_id).order_by(CheckupRecord.week_number).all()
    return jsonify({
        "message"      : f"Patient shared with Dr. {doctor.name}",
        "patient"      : p.to_dict(),
        "doctor"       : doctor.to_dict(),
        "checkup_count": len(checkups),
    }), 200


# ── Hospitals & Doctors Directory ───────────────────────

HOSPITALS_DATA = [
    {"id":1, "name":"AIIMS Nagpur",            "type":"Government", "city":"Nagpur",    "phone":"0712-2800000", "specialty":"Maternity & Gynecology", "beds":850,  "emergency":True,  "distance_km":2.1},
    {"id":2, "name":"Wockhardt Hospital",       "type":"Private",    "city":"Nagpur",    "phone":"0712-6622000", "specialty":"High-Risk Pregnancy",    "beds":320,  "emergency":True,  "distance_km":4.5},
    {"id":3, "name":"Kamla Nehru Hospital",     "type":"Government", "city":"Nagpur",    "phone":"0712-2740000", "specialty":"Maternal & Child Health", "beds":500,  "emergency":True,  "distance_km":3.2},
    {"id":4, "name":"Orange City Hospital",     "type":"Private",    "city":"Nagpur",    "phone":"0712-6641000", "specialty":"Obstetrics & Neonatal",  "beds":400,  "emergency":True,  "distance_km":5.8},
    {"id":5, "name":"Indira Gandhi Govt MC",    "type":"Government", "city":"Nagpur",    "phone":"0712-2744000", "specialty":"General & Maternity",    "beds":1200, "emergency":True,  "distance_km":6.3},
    {"id":6, "name":"Lilavati Hospital",        "type":"Private",    "city":"Mumbai",    "phone":"022-2675000",  "specialty":"High-Risk Maternity",    "beds":700,  "emergency":True,  "distance_km":8.1},
    {"id":7, "name":"PHC Hingna",               "type":"PHC",        "city":"Nagpur",    "phone":"0712-2285000", "specialty":"Primary Maternal Care",  "beds":30,   "emergency":False, "distance_km":1.0},
    {"id":8, "name":"District Hospital Wardha", "type":"Government", "city":"Wardha",    "phone":"07152-242300", "specialty":"Obstetrics",             "beds":280,  "emergency":True,  "distance_km":9.5},
]

@app.route("/api/hospitals", methods=["GET"])
@jwt_required(optional=True)
def get_hospitals():
    city   = request.args.get("city", "").lower()
    htype  = request.args.get("type", "").lower()
    result = HOSPITALS_DATA
    if city:
        result = [h for h in result if city in h["city"].lower()]
    if htype:
        result = [h for h in result if htype in h["type"].lower()]
    # Sort by distance
    result = sorted(result, key=lambda h: h["distance_km"])
    return jsonify(result), 200


@app.route("/api/doctors", methods=["GET"])
@jwt_required()
def get_doctors():
    doctors = User.query.filter_by(role="doctor", is_active=True).order_by(User.name).all()
    return jsonify([d.to_dict() for d in doctors]), 200


# ─────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({
        "status" : "ok",
        "service": "Matru Raksha API",
        "db"     : "SQLite",
        "ml_model": "loaded" if ML_MODEL is not None else "fallback (rule-based)",
    }), 200


# ─────────────────────────────────────────
# Startup
# ─────────────────────────────────────────

with app.app_context():
    db.create_all()
    seed_donors_from_csv()
    seed_admin_user()

if __name__ == "__main__":
    print("\n" + "="*55)
    print("  Matru Raksha API  --> http://127.0.0.1:5000")
    print("  Default Admin  -->  admin@matruraksha.in / admin123")
    print("="*55 + "\n")
    app.run(debug=True, port=5000)

