from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_health():
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "UP"
    assert data["model_loaded"] is True
    print("[PASS] /health test:", data)

def test_predict_normal():
    payload = {
        "age": 25,
        "systolic_bp": 110,
        "diastolic_bp": 70,
        "blood_glucose": 6.2,
        "body_temperature": 98.4,
        "heart_rate": 72
    }
    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] in ["Low Risk", "Medium Risk", "High Risk"]
    assert "probabilities" in data
    assert "confidence" in data
    assert data["is_mock"] is False
    print("[PASS] /predict normal test:", data["risk_level"], "confidence:", data["confidence"])

def test_predict_high_risk():
    payload = {
        "age": 38,
        "systolic_bp": 160,
        "diastolic_bp": 100,
        "blood_glucose": 15.0,
        "body_temperature": 101.5,
        "heart_rate": 95
    }
    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["risk_level"] == "High Risk"
    print("[PASS] /predict high risk test:", data["risk_level"], "confidence:", data["confidence"])

if __name__ == "__main__":
    test_health()
    test_predict_normal()
    test_predict_high_risk()
    print("ALL ML SERVICE TESTS PASSED SUCCESSFULLY!")
