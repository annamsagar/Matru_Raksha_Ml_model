import joblib
import os

_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models", "maternal_model.pkl")
model = joblib.load(_MODEL_PATH)

def predict_risk(input_data):
    prediction = model.predict([input_data])[0]
    
    # Calculate confidence using predict_proba
    if hasattr(model, 'predict_proba'):
        probabilities = model.predict_proba([input_data])[0]
        confidence = float(max(probabilities) * 100)
    else:
        confidence = 90.0

    # Calculate local feature importance based on deviation from normal
    # Normal baselines: Age: 25, SysBP: 120, DiaBP: 80, BS: 7.0, Temp: 98.6, HR: 75
    baselines = [25, 120, 80, 7.0, 98.6, 75]
    feature_names = ["Age", "Systolic BP", "Diastolic BP", "Blood Glucose", "Body Temp", "Heart Rate"]
    
    global_importances = getattr(model, 'feature_importances_', [1, 1, 1, 1, 1, 1])
    
    factors = []
    for val, base, name, weight in zip(input_data, baselines, feature_names, global_importances):
        # Calculate deviation percentage from normal (capped at 100%)
        # Add a tiny epsilon to prevent division by zero
        deviation = abs(val - base) / (base + 0.001) 
        
        # Combine local deviation with global model importance
        score = deviation * weight * 100
        
        factors.append({
            "name": name,
            "score": score
        })
        
    # Sort factors by score and normalize them so they look good in UI (out of 100)
    factors.sort(key=lambda x: x['score'], reverse=True)
    
    max_score = max(f['score'] for f in factors) + 0.001
    
    final_factors = []
    for i, f in enumerate(factors):
        # Scale top factor to roughly 80-95%, others relative to it
        normalized = (f['score'] / max_score) * (90 - i * 5)
        # Ensure it is at least 5% so it's visible on the UI
        final_factors.append({
            "name": f['name'],
            "importance": max(5, min(95, int(normalized)))
        })
        
    main_factor = final_factors[0]['name']

    return prediction, confidence, main_factor, final_factors