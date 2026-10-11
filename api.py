from flask import Flask, request, jsonify
from utils.predictor import predict_risk

app = Flask(__name__)

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    try:
        print("Received data from Spring Boot:", data)
        
        # Convert mg/dL to mmol/L for BS
        bs_val = data.get('bs')
        if bs_val is not None and bs_val > 30: # If it's already small, maybe it's already mmol/L, but frontend uses mg/dL (50-300)
            bs_val = bs_val / 18.0
            
        # Convert Celsius to Fahrenheit for Temp
        temp_val = data.get('temp')
        if temp_val is not None and temp_val < 50: # If it's < 50, it's Celsius (frontend uses 35-42)
            temp_val = (temp_val * 9/5) + 32
            
        features = [
            data.get('age', 25),
            data.get('sys_bp', 120),
            data.get('dia_bp', 80),
            bs_val if bs_val else 7.0,
            temp_val if temp_val else 98.6,
            data.get('hr', 75)
        ]
        
        print("Features passed to model:", features)
        prediction, confidence, main_factor, factors = predict_risk(features)
        
        # In scikit-learn, prediction is usually an array, e.g., [1]
        pred_val = int(prediction[0]) if isinstance(prediction, (list, tuple)) or hasattr(prediction, '__iter__') else int(prediction)
        
        risk_map = {
            0: "Low Risk",
            1: "Medium Risk",
            2: "High Risk"
        }
        
        return jsonify({
            'prediction': pred_val,
            'risk_level': risk_map.get(pred_val, "Unknown"),
            'confidence': confidence,
            'main_factor': main_factor,
            'factors': factors
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400

if __name__ == '__main__':
    app.run(port=5000, debug=True)
