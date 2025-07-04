import json
import os
import gspread
import time
from oauth2client.service_account import ServiceAccountCredentials
from db import SessionLocal
from models import License, AccountStatus, Base
from sqlalchemy import create_engine
from db import engine
from google.oauth2.service_account import Credentials

RAW_JSON = os.getenv("GOOGLE_CREDENTIALS")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")  # ID del Google Sheet desde la URL
WORKSHEET_NAME = os.getenv("WORKSHEET_NAME")

if not RAW_JSON:
    raise ValueError("❌ Variable de entorno GOOGLE_CREDENTIALS no está definida")

Base.metadata.create_all(bind=engine)

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_dict = json.loads(RAW_JSON)
creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

def sync_sheet_to_db():
    print("🔄 Sync: Google Sheets ➡️ PostgreSQL")
    records = sheet.get_all_records()
    db = SessionLocal()
    try:
        db.query(License).delete()
        for row in records:
            license = License(
                account_number=str(row["account_number"]),
                license_key=row["license_key"],
                enabled=str(row["enabled"]).lower() == "true"
            )
            db.add(license)
        db.commit()
        print("✅ Licencias sincronizadas")
    finally:
        db.close()

def sync_db_to_sheet():
    print("🔄 Sync: PostgreSQL ➡️ Google Sheets")
    db = SessionLocal()
    try:
        data = db.query(AccountStatus).all()
        header = ["account_number", "account_balance", "last_trade", "account_mode", "broker_server", "broker_company", "risk_per_group", "ea_status"]
        values = [header]
        for item in data:
            values.append([
                item.account_number,
                item.account_balance,
                item.last_trade,
                item.account_mode,
                item.broker_server,
                item.broker_company,
                item.risk_per_group,
                item.ea_status
            ])
        sheet.clear()
        sheet.update(values)
        print("✅ Estado de cuentas actualizado en Google Sheets")
    finally:
        db.close()

def run_sync():
    while True:
        sync_sheet_to_db()
        time.sleep(3)
        sync_db_to_sheet()
        time.sleep(60)  # Espera 1 minuto para el próximo ciclo
