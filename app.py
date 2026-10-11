import streamlit as st
from utils.predictor import predict_risk
from utils.donor_match import find_donors

st.set_page_config(page_title="Matru Raksha", layout="centered")

st.title("🛡️ Matru Raksha")
st.subheader("AI-Driven Maternal Risk Monitoring & Smart Blood Donor Network")

st.markdown("---")

# -------------------------
# Patient Details Section
# -------------------------

st.header("👩‍⚕️ Enter Patient Details")

age = st.number_input("Age", min_value=18, max_value=50, step=1)

sys_bp = st.number_input("Systolic BP", min_value=80, max_value=200)

dia_bp = st.number_input("Diastolic BP", min_value=50, max_value=150)

bs = st.number_input("Blood Sugar (mg/dL)", min_value=50, max_value=300)

temp = st.number_input("Body Temperature (°F)", min_value=95.0, max_value=105.0)

hr = st.number_input("Heart Rate (bpm)", min_value=40, max_value=150)

blood_group = st.selectbox(
    "Patient Blood Group",
    ["A+","A-","B+","B-","O+","O-","AB+","AB-"]
)

st.markdown("---")

# -------------------------
# Prediction Button
# -------------------------

if st.button("🔍 Predict Risk"):

    input_data = [age, sys_bp, dia_bp, bs, temp, hr]

    prediction = predict_risk(input_data)

    risk_map = {
        0: "Low Risk 🟢",
        1: "Medium Risk 🟡",
        2: "High Risk 🔴"
    }

    st.success(f"Predicted Risk Level: {risk_map[prediction]}")

    # -------------------------
    # Emergency Donor Matching
    # -------------------------

    if prediction == 2:
        st.warning("⚠ High Risk Detected! Initiating Emergency Donor Search...")

        matched_donors = find_donors(blood_group)

        if not matched_donors.empty:
            st.subheader("🩸 Available Matching Donors")
            st.dataframe(matched_donors)
        else:
            st.error("No eligible donors found nearby.")