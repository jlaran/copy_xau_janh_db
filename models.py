from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String

Base = declarative_base()

class License(Base):
    __tablename__ = "licenses"

    account_number = Column(String, primary_key=True)
    license_key = Column(String)
    enabled = Column(String)

class AccountStatus(Base):
    __tablename__ = "account_status"

    account_number = Column(String, primary_key=True)
    account_balance = Column(String)
    last_trade = Column(String)
    account_mode = Column(String)
    broker_server = Column(String)
    broker_company = Column(String)
    risk_per_group = Column(String)
    ea_status = Column(String)
    last_sync = Column(String)