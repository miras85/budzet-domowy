from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey, DECIMAL, Boolean, DateTime, UniqueConstraint, Index
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
    bban = Column(String(50), nullable=True)
    # Limit debetu (overdraft) konta — ING nie wystawia go przez API (credit_limit=None),
    # więc konfigurujemy ręcznie. Potrzebny do wyliczenia zablokowanych środków:
    #   blokady = saldo_booked (ITBD) + overdraft_limit − saldo_available (ITAV)
    overdraft_limit = Column(DECIMAL(10, 2), default=0.0)
    # Zablokowane środki (blokady kartowe) policzone z sald ING przy ostatnim imporcie.
    # Migawka — odświeżana przy każdym imporcie. Wartość zbiorcza na koncie.
    blocked_funds = Column(DECIMAL(10, 2), default=0.0)
    # Enable Banking uid konta (mapowanie uid→nasze konto). Zapamiętane raz z /details,
    # żeby przy imporcie nie wołać /details ani /balances dla każdego konta osobno.
    # Salda (dla blokad) pobieramy tylko dla konta z debetem (RÓR) → 1 zapytanie/import.
    enable_banking_uid = Column(String(64), nullable=True)

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
    bank_reference = Column(String(255), nullable=True, index=True)

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
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

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

class LearnedPattern(Base):
    """
    Nauczone dopasowania sprzedawca -> kategoria (per użytkownik).
    Jeden wiersz na (user_id, merchant_token, category_id) z licznikiem trafień.
    Przy sugestii wybieramy kategorię o NAJWYŻSZYM hit_count (najczęstszą),
    a nie ostatnią. Dzięki temu pojedyncza pomyłka nie psuje wzorca.
    """
    __tablename__ = "learned_patterns"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    merchant_token = Column(String(100), nullable=False)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False)
    hit_count = Column(Integer, default=1, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint('user_id', 'merchant_token', 'category_id',
                         name='uq_learned_user_token_cat'),
        Index('ix_learned_patterns_lookup', 'user_id', 'merchant_token'),
    )


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
    sync_count_today = Column(Integer, default=0, nullable=False)
    sync_count_date = Column(Date, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
