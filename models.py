from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DECIMAL, Boolean
from sqlalchemy.orm import relationship
from database import Base

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    type = Column(String(50))
    balance = Column(DECIMAL(10, 2), default=0.0)
    is_savings = Column(Boolean, default=False)

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True)
    # Scalono pole z drugiej definicji:
    monthly_limit = Column(DECIMAL(10, 2), default=0.0)

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    total_amount = Column(DECIMAL(10, 2))
    remaining_amount = Column(DECIMAL(10, 2))
    monthly_payment = Column(DECIMAL(10, 2))
    next_payment_date = Column(Date)

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    target_amount = Column(DECIMAL(10, 2))
    current_amount = Column(DECIMAL(10, 2), default=0.0)
    deadline = Column(Date)
    is_archived = Column(Boolean, default=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)

class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    amount = Column(DECIMAL(10, 2))
    description = Column(String(255))
    date = Column(Date)
    type = Column(String(20))
    status = Column(String(20), default="zrealizowana")
    
    account_id = Column(Integer, ForeignKey("accounts.id"))
    target_account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    loan_id = Column(Integer, ForeignKey("loans.id"), nullable=True)

    account = relationship("Account", foreign_keys=[account_id])
    target_account = relationship("Account", foreign_keys=[target_account_id])
    category = relationship("Category")
    loan = relationship("Loan")

class PaydayOverride(Base):
    __tablename__ = "payday_overrides"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer)
    month = Column(Integer)
    day = Column(Integer)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))

class RecurringTransaction(Base):
    __tablename__ = "recurring_transactions"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    amount = Column(DECIMAL(10, 2))
    day_of_month = Column(Integer)
    last_run_date = Column(Date, nullable=True)
    is_active = Column(Boolean, default=True)
    
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    
    category = relationship("Category")
    account = relationship("Account")
