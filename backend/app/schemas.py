from pydantic import BaseModel
from datetime import datetime, date
from typing import Optional

class Token(BaseModel):
    access_token: str
    token_type: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    real_name: str
    role: str = "operator"

class UserOut(BaseModel):
    id: int
    username: str
    real_name: str
    role: str
    status: int
    last_login: Optional[datetime] = None
    class Config:
        from_attributes = True

class VehicleBase(BaseModel):
    plate_number: str
    brand_model: str
    color: Optional[str] = None
    purchase_date: Optional[date] = None
    insurance_expire: Optional[date] = None
    status: int = 1

class VehicleOut(VehicleBase):
    id: int
    create_time: datetime
    class Config:
        from_attributes = True

class DriverBase(BaseModel):
    name: str
    gender: Optional[str] = None
    id_card: str
    license_no: str
    qualification_no: Optional[str] = None
    phone: Optional[str] = None
    hire_date: Optional[date] = None
    status: int = 1

class DriverOut(DriverBase):
    id: int
    class Config:
        from_attributes = True

class OperationRecordCreate(BaseModel):
    order_no: str
    vehicle_id: int
    driver_id: int
    start_time: datetime
    end_time: datetime
    loaded_mileage: float
    empty_mileage: float
    amount: float
    pay_type: Optional[str] = None

class OperationRecordOut(OperationRecordCreate):
    id: int
    create_time: datetime
    class Config:
        from_attributes = True