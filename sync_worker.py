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

scope = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]
creds_dict = json.loads(RAW_JSON)
creds = Credentials.from_service_account_info(
    creds_dict,
    scopes=scope
)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)


def sync_sheet_to_db():
    print("🔄 Sync: Google Sheets ➡️ PostgreSQL")
    db = SessionLocal()
    rows = sheet.get_all_records()

    for row in rows:
        # Validar que la fila tenga un account_number no vacío
        account_number = str(row.get("account_number", "")).strip()
        if not account_number:
            continue  # Saltar filas vacías o sin cuenta

        # Crear o actualizar registro
        license = db.query(License).filter_by(account_number=account_number).first()
        if license:
            license.license_key = row.get("license_key", "").strip()
            license.enabled = str(row.get("enabled", "False")).lower() == "true"
        else:
            new_license = License(
                account_number=account_number,
                license_key=row.get("license_key", "").strip(),
                enabled=str(row.get("enabled", "False")).lower() == "true"
            )
            db.add(new_license)

    db.commit()
    db.close()
    print("✅ Sincronización completa.")


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
