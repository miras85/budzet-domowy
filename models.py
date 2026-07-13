from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DECIMAL, Boolean, DateTime
from datetime import datetime
from sqlalchemy.orm import relationship
from database import Base
from datetime import date

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    hashed_password = Column(String(255))
    role = Column(String(20), default="admin", nullable=False)
    invited_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    accounts = relationship("Account", back_populates="user")
    categories = relationship("Category", back_populates="user")
    loans = relationship("Loan", back_populates="user")
    goals = relationship("Goal", back_populates="user")
    recurring_transactions = relationship("RecurringTransaction", back_populates="user")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    type = Column(String(50))
    balance = Column(DECIMAL(10, 2), default=0.0)
    is_savings = Column(Boolean, default=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="accounts")

class Category(Base):
    __tablename__ = "categories"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    monthly_limit = Column(DECIMAL(10, 2), default=0.0)
    icon_name = Column(String(50), default="tag")
    color = Column(String(20), default="#94a3b8")
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="categories")

class Loan(Base):
    __tablename__ = "loans"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    total_amount = Column(DECIMAL(10, 2))
    remaining_amount = Column(DECIMAL(10, 2))
    monthly_payment = Column(DECIMAL(10, 2))
    next_payment_date = Column(Date)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="loans")

class Goal(Base):
    __tablename__ = "goals"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100))
    target_amount = Column(DECIMAL(10, 2))
    current_amount = Column(DECIMAL(10, 2), default=0.0)
    deadline = Column(Date)
    is_archived = Column(Boolean, default=False)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="goals")

class GoalContribution(Base):
    __tablename__ = "goal_contributions"
    id = Column(Integer, primary_key=True, index=True)
    goal_id = Column(Integer, ForeignKey("goals.id"))
    amount = Column(DECIMAL(10, 2))
    date = Column(Date, default=date.today)

    goal = relationship("Goal")

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", back_populates="recurring_transactions")
    category = relationship("Category")
    account = relationship("Account")

class Invitation(Base):
    __tablename__ = "invitations"
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(64), unique=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    used = Column(Boolean, default=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    creator = relationship("User", foreign_keys=[created_by])

class UserDataAccess(Base):
    __tablename__ = "user_data_access"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    user = relationship("User", foreign_keys=[user_id])
    owner = relationship("User", foreign_keys=[owner_id])

class BankSession(Base):
    __tablename__ = "bank_sessions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    session_id = Column(String(255), nullable=True)
    bank_name = Column(String(100), nullable=False)
    bank_country = Column(String(10), default="PL")
    status = Column(String(50), default="pending")
    valid_until = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_sync = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
