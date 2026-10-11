import os
import joblib
import pandas as pd
from datetime import datetime, timezone
from typing import Optional, Dict, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(
    title="Matru Raksha ML Service",
    description="Maternal Health Risk Prediction REST API powered by Random Forest Classifier",
    version="1.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MODEL_VERSION = "RandomForest-150-v1.0"
MODEL_PATH = os.getenv(
    "MODEL_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "maternal_model.pkl")
)

# Attempt to load model
model = None
is_mock_mode = False

if os.path.exists(MODEL_PATH):
    try:
        model = joblib.load(MODEL_PATH)
        print(f"[ML Service] Successfully loaded model from {MODEL_PATH}")
    except Exception as e:
        print(f"[ML Service] Error loading model from {MODEL_PATH}: {e}")
        is_mock_mode = True
else:
    print(f"[ML Service] Model not found at {MODEL_PATH}. Running in clearly-labelled development mock mode.")
    is_mock_mode = True


class HealthCheckResponse(BaseModel):
    status: str
    service: str
    model_loaded: bool
    is_mock_mode: bool
    model_version: str
    timestamp: str


class PredictionRequest(BaseModel):
    # 6 features in exact logical order:
    # 1. Age, 2. Systolic BP, 3. Diastolic BP, 4. Blood Glucose, 5. Body Temp, 6. Heart Rate
    age: int = Field(25, ge=10, le=75, description="Patient age in years (10 - 75)")
    systolic_bp: Optional[float] = Field(None, description="Systolic Blood Pressure in mmHg")
    diastolic_bp: Optional[float] = Field(None, description="Diastolic Blood Pressure in mmHg")
    blood_glucose: Optional[float] = Field(None, description="Blood Glucose")
    body_temperature: Optional[float] = Field(None, description="Body Temperature")
    heart_rate: Optional[float] = Field(None, description="Heart Rate in bpm")
    glucose_unit: Optional[str] = Field("mmol/L", description="Unit for blood glucose ('mmol/L' or 'mg/dL')")
    temp_unit: Optional[str] = Field("F", description="Unit for body temperature ('F' or 'C')")

    # Compatibility aliases for Spring Boot payload
    sys_bp: Optional[float] = None
    dia_bp: Optional[float] = None
    bs: Optional[float] = None
    temp: Optional[float] = None
    hr: Optional[float] = None


class RiskFactor(BaseModel):
    name: str
    importance: int


class PredictionResponse(BaseModel):
    prediction: int
    risk_level: str
    confidence: float
    probabilities: Dict[str, float]
    main_factor: str
    factors: List[RiskFactor]
    model_version: str
    is_mock: bool
    timestamp: str
    medical_disclaimer: str


RISK_MAP = {
    0: "Low Risk",
    1: "Medium Risk",
    2: "High Risk"
}


@app.get("/health", response_model=HealthCheckResponse)
def health_check():
    return {
        "status": "UP",
        "service": "Matru-Raksha-ML-FastAPI",
        "model_loaded": model is not None,
        "is_mock_mode": is_mock_mode,
        "model_version": MODEL_VERSION,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


@app.get("/model-info")
def model_info():
    return {
        "model_type": "RandomForestClassifier",
        "n_estimators": 150,
        "feature_order": ["Age", "SystolicBP", "DiastolicBP", "BS", "BodyTemp", "HeartRate"],
        "class_mapping": {"0": "Low Risk", "1": "Medium Risk", "2": "High Risk"},
        "model_version": MODEL_VERSION,
        "is_mock": is_mock_mode,
        "path": MODEL_PATH
    }


@app.post("/predict", response_model=PredictionResponse)
def predict(req: PredictionRequest):
    # Normalize inputs
    age = req.age if req.age is not None else 25
    sys_bp = req.sys_bp if req.sys_bp is not None else (req.systolic_bp if req.systolic_bp is not None else 120.0)
    dia_bp = req.dia_bp if req.dia_bp is not None else (req.diastolic_bp if req.diastolic_bp is not None else 80.0)
    bs = req.bs if req.bs is not None else (req.blood_glucose if req.blood_glucose is not None else 7.0)
    temp = req.temp if req.temp is not None else (req.body_temperature if req.body_temperature is not None else 98.6)
    hr = req.hr if req.hr is not None else (req.heart_rate if req.heart_rate is not None else 75.0)

    # Convert glucose from mg/dL to mmol/L if needed
    if req.glucose_unit == "mg/dL" or bs > 30.0:
        bs_mmol = bs / 18.0
    else:
        bs_mmol = bs

    # Convert temperature from Celsius to Fahrenheit if needed
    if req.temp_unit == "C" or temp < 50.0:
        temp_f = (temp * 9.0 / 5.0) + 32.0
    else:
        temp_f = temp

    # Prepare DataFrame matching trained model's feature names
    features_df = pd.DataFrame([{
        "Age": float(age),
        "SystolicBP": float(sys_bp),
        "DiastolicBP": float(dia_bp),
        "BS": float(bs_mmol),
        "BodyTemp": float(temp_f),
        "HeartRate": float(hr)
    }])

    now_iso = datetime.now(timezone.utc).isoformat()
    disclaimer = (
        "ML-generated risk estimate only. Not a medical diagnosis. "
        "Urgent maternal symptoms require immediate professional clinical care."
    )

    if model is not None and not is_mock_mode:
        try:
            pred_class = int(model.predict(features_df)[0])
            probs_list = model.predict_proba(features_df)[0]
            
            # Map probabilities
            class_probs = {
                "Low Risk": round(float(probs_list[0]), 4),
                "Medium Risk": round(float(probs_list[1]), 4),
                "High Risk": round(float(probs_list[2]), 4)
            }
            confidence = round(float(max(probs_list)) * 100.0, 1)

            # Feature deviation analysis
            baselines = [25.0, 120.0, 80.0, 7.0, 98.6, 75.0]
            names = ["Age", "Systolic BP", "Diastolic BP", "Blood Glucose", "Body Temp", "Heart Rate"]
            inputs = [float(age), float(sys_bp), float(dia_bp), float(bs_mmol), float(temp_f), float(hr)]
            importances = getattr(model, "feature_importances_", [1, 1, 1, 1, 1, 1])

            factors = []
            for val, base, name, weight in zip(inputs, baselines, names, importances):
                dev = abs(val - base) / (base + 0.001)
                score = dev * weight * 100.0
                factors.append({"name": name, "score": score})

            factors.sort(key=lambda x: x["score"], reverse=True)
            max_s = max(f["score"] for f in factors) + 0.001

            formatted_factors = []
            for i, f in enumerate(factors):
                normalized = (f["score"] / max_s) * (92 - i * 5)
                formatted_factors.append({
                    "name": f["name"],
                    "importance": max(5, min(95, int(normalized)))
                })

            main_factor = formatted_factors[0]["name"]

            return {
                "prediction": pred_class,
                "risk_level": RISK_MAP.get(pred_class, "Unknown"),
                "confidence": confidence,
                "probabilities": class_probs,
                "main_factor": main_factor,
                "factors": formatted_factors,
                "model_version": MODEL_VERSION,
                "is_mock": False,
                "timestamp": now_iso,
                "medical_disclaimer": disclaimer
            }
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Model inference error: {str(e)}"
            )
    else:
        # Development-only mock response (explicitly flagged, never fabricated as real clinical assessment)
        mock_pred = 0 if sys_bp < 130 and bs_mmol < 8.0 else (2 if sys_bp >= 140 or bs_mmol >= 11.0 else 1)
        return {
            "prediction": mock_pred,
            "risk_level": RISK_MAP[mock_pred],
            "confidence": 75.0,
            "probabilities": {"Low Risk": 0.6, "Medium Risk": 0.3, "High Risk": 0.1},
            "main_factor": "Systolic BP",
            "factors": [
                {"name": "Systolic BP", "importance": 85},
                {"name": "Blood Glucose", "importance": 65},
                {"name": "Age", "importance": 40}
            ],
            "model_version": "DEV-MOCK-ONLY-DO-NOT-USE-CLINICALLY",
            "is_mock": True,
            "timestamp": now_iso,
            "medical_disclaimer": disclaimer
        }
