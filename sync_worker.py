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
from datetime import datetime

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

def sync_sheet_to_db(sheet_data):
    print("🔄 Sync: Google Sheets ➡️ PostgreSQL")
    db = SessionLocal()

    for row in sheet_data:
        account_number = str(row.get("account_number", "")).strip()
        if not account_number:
            continue

        # LICENCIA
        license_obj = db.query(License).filter_by(account_number=account_number).first()
        if license_obj:
            license_obj.license_key = str(row.get("license_key", "")).strip()
            license_obj.enabled = str(row.get("enabled", "")).strip().lower()
        else:
            db.add(License(
                account_number=account_number,
                license_key=row.get("license_key", "").strip(),
                enabled=str(row.get("enabled", "")).strip().lower()
            ))

        # ACCOUNT STATUS
        status_obj = db.query(AccountStatus).filter_by(account_number=account_number).first()
        if not status_obj:
            db.add(AccountStatus(
                account_number=account_number,
                account_balance=str(row.get("account_balance", "")).strip(),
                last_trade=str(row.get("last_trade", "")).strip(),
                account_mode=str(row.get("account_mode", "")).strip(),
                broker_server=str(row.get("broker_server", "")).strip(),
                broker_company=str(row.get("broker_company", "")).strip(),
                risk_per_group=str(row.get("risk_per_group", "")).strip(),
                ea_status=str(row.get("ea_status", "")).strip(),
                last_sync=str(row.get("last_sync", "")).strip()
            ))

    db.commit()
    db.close()
    print("✅ Sincronización desde Google Sheets completada.")

def sync_db_to_sheet(sheet_data):
    print("🔄 Sync: PostgreSQL ➡️ Google Sheets")
    db = SessionLocal()
    try:
        db_data = db.query(AccountStatus).all()

        if not sheet_data:
            print("❌ La hoja está vacía. Asegúrate de tener encabezados.")
            return

        header = sheet_data[0]
        col_index = {col: i for i, col in enumerate(header)}

        updatable_columns = [
            "account_balance", "last_trade", "account_mode",
            "broker_server", "broker_company", "risk_per_group", "ea_status", "last_sync"
        ]

        sheet_rows_by_account = {
            row[col_index["account_number"]]: (i, row)
            for i, row in enumerate(sheet_data[1:], start=2)
        }

        for item in db_data:
            account_id = str(item.account_number)
            if account_id in sheet_rows_by_account:
                row_number, current_row = sheet_rows_by_account[account_id]

                for column in updatable_columns:
                    new_value = str(getattr(item, column))
                    col_pos = col_index[column]
                    current_cell_value = current_row[col_pos] if col_pos < len(current_row) else ""

                    if current_cell_value != new_value:
                        cell_range = f"{chr(65 + col_pos)}{row_number}"
                        sheet.update(cell_range, [[new_value]])
                        print(f"✏️ {account_id} - {column} actualizado en {cell_range}")
            else:
                print(f"➕ Cuenta en DB no está en hoja: {account_id}")
    finally:
        db.close()

def run_sync():
    while True:
        try:
            print("📥 Leyendo hoja de cálculo...")
            expected_headers = [
                "account_number", "license_key", "enabled", "account_balance", "last_trade",
                "account_mode", "broker_server", "broker_company", "risk_per_group", "ea_status"
            ]
            sheet_data = sheet.get_all_records(expected_headers=expected_headers)
            sync_sheet_to_db(sheet_data)

            print("📤 Releyendo hoja como valores brutos para sincronizar desde DB...")
            sheet_data_raw = sheet.get_all_values()
            sync_db_to_sheet(sheet_data_raw)

        except Exception as e:
            print(f"❌ Error durante la sincronización: {e}")
            log("❌ Error durante la sincronización:")

        print("⏳ Esperando 60 segundos para el próximo ciclo...\n")
        log("⏳ Esperando 60 segundos para el próximo ciclo...\n")
        time.sleep(60)

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")