from pydantic import BaseModel
from typing import Optional
from datetime import date

# --- DTO (Data Transfer Objects) ---

class UserCreate(BaseModel):
    username: str
    password: str

class PasswordChange(BaseModel):
    old_password: str
    new_password: str

class TransactionCreate(BaseModel):
    amount: float
    description: str
    date: date
    type: str
    account_id: int
    target_account_id: Optional[int] = None
    category_name: Optional[str] = None
    loan_id: Optional[int] = None
    status: str = "zrealizowana"

class AccountUpdate(BaseModel):
    name: str
    type: str
    balance: float
    is_savings: bool = False

class LoanCreate(BaseModel):
    name: str
    total_amount: float
    remaining_amount: float
    monthly_payment: float
    next_payment_date: date

class LoanUpdate(BaseModel):
    name: str
    total_amount: float
    remaining_amount: float
    monthly_payment: float
    next_payment_date: date

class PaydayOverrideCreate(BaseModel):
    year: int
    month: int
    day: int

class CategoryCreate(BaseModel):
    name: str

class GoalCreate(BaseModel):
    name: str
    target_amount: float
    deadline: date
    account_id: int

class GoalFund(BaseModel):
    amount: float
    source_account_id: int
    target_savings_id: Optional[int] = None

class GoalTransfer(BaseModel):
    amount: float
    target_goal_id: int
