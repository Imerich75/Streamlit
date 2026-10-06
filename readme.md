📊 Cyber Risk Forecast Dashboard (2025–2030)
Interactive visual analytics app predicting future cyber attack risk across countries from 2025 to 2030, using enriched global datasets and machine learning.

Built with Streamlit, powered by open data and Random Forest models.


🚀 Live Demo
👉 Launch the app on Streamlit Community Cloud

🔍 Key Features
📈 Forecast Visualization: Projected attack counts by country from 2025 to 2030

🌍 Global Choropleth Mapping with log-scaled visual cues

📊 Vanilla BI module: Simple bar/pie charts for non-technical audiences

🧠 AI-powered predictions: Based on Random Forest regression trained on historical exposure, GDP, internet metrics, and population data

📁 Fully modular architecture for fast updates and future expansion

🧠 Methodology
Data Merge from multiple sources: cyber incidents, GDP, internet usage, population, etc.

Feature Engineering with custom exposure indexes and threat scores

Random Forest Regression model trained on pre-2025 data

Linear Extrapolation of features into 2025–2030

Prediction Output saved into future_predictions.csv

Dashboard Visuals rendered directly from static outputs – fast and safe

📦 Datasets Used
UMD Cyber Attack Dataset

World Bank GDP & Population data

Internet usage & infrastructure stats (ITU, UN, open sources)

Magyar Közút – Előzetes ÉÁNF táblázat 2025 (forgalom/, processed by 6forgalom_prep.py); county boundaries from wuerdo/geoHungary

🛠 Installation
bash
Copy
Edit
git clone https://github.com/Imerich75/Streamlit
cd cyber-risk-dashboard
pip install -r requirements.txt
streamlit run app.py
🌐 Requirements
Python 3.8+

Streamlit

pandas, numpy, plotly

scikit-learn (for offline retraining)

📌 App Modules
Page	Purpose
Vanilla BI	Simple charts for GDP, risk metrics
Risk Discrepancy	Visualizing model bias & anomalies
Transparency Map	Detection of underreporting
Threat Explorer	Custom scatter visualizations
Log Insights	Log-scaled metrics across dimensions
2025–2030 Forecast	Future attack projections (no retraining)
Data Browser	Table-based preview of full dataset
Forgalmi Térkép	Hungarian national road traffic (Magyar Közút preliminary ÉÁNF 2025): county map, busiest roads, road profile, vehicle mix
📃 License
MIT — free for educational, research and public use.

🤝 Acknowledgements
Special thanks to:

Streamlit for the framework

PyCountry, Scikit-learn, and Plotly

UMD Center for International & Security Studies (data source inspiration)
