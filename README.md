# Frostline ❄️
Frostline is a personal project built to explore cold-chain logistics, temperature risks, and warehouse inventory management. It uses sensor data and synthetic warehouse records to analyse temperature issues and test different recovery scenarios.
### Features
- **Thermal Monitoring:** Cleans sensor data and identifies missing readings and temperature excursions.
- **Warehouse & Inventory:** Generates sample products, storage zones, batches, and orders.
- **Risk Screening:** Flags inventory batches for further review using rule-based checks.
- **Relocation Planning:** Compares warehouse relocation strategies.
- **Order Rescue:** Simulates order fulfilment using priority and First-Expiry-First-Out (FEFO) rules.
- **Cooling Failure:** Simulates cooling disruptions and temperature recovery.
- **Uncertainty & Audit:** Compares scenarios and records simulation results.
- **Data Quality:** Reviews data quality reports and validation checks.
### Tech Stack
- Python
- Pandas
- Streamlit
- Matplotlib
- CSV datasets and reports
### Run Locally
Install the required packages:
```bash
pip install streamlit pandas matplotlib
```
Run the application:
```bash
streamlit run app.py
```
### Note
Frostline is a decision-support prototype. It uses historical sensor data, synthetic warehouse records, rule-based risk screening, and simulated scenarios. Its outputs are for analysis and experimentation, not real-world product safety approval.
