import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report

# Load dataset
df = pd.read_csv("data/dataset.csv")

# Features
X = df[['Age','SystolicBP','DiastolicBP','BS','BodyTemp','HeartRate']]

# Target
y = df['RiskLevel']
y = y.map({'low risk':0, 'mid risk':1, 'high risk':2})

# Train Test Split
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42
)

# Train Model
model = RandomForestClassifier(n_estimators=150, random_state=42)
model.fit(X_train, y_train) #80%

# Evaluate
y_pred = model.predict(X_test)
print(classification_report(y_test, y_pred)) #20%

# Save model inside models folder
joblib.dump(model, "models/maternal_model.pkl")

print("Model Saved Successfully!")