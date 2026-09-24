from sqlalchemy import Column, BigInteger, String, Date, DateTime, Numeric, Integer, ForeignKey, CHAR
from sqlalchemy.orm import relationship
from datetime import datetime
from .database import Base

class Vehicle(Base):
    __tablename__ = "vehicle"
    id = Column(BigInteger, primary_key=True, index=True)
    plate_number = Column(String(20), unique=True, nullable=False)
    brand_model = Column(String(50), nullable=False)
    color = Column(String(20))
    purchase_date = Column(Date)
    insurance_expire = Column(Date)
    status = Column(Integer, default=1)
    create_time = Column(DateTime, default=datetime.utcnow)
    operation_records = relationship("OperationRecord", back_populates="vehicle")

class Driver(Base):
    __tablename__ = "driver"
    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(30), nullable=False)
    gender = Column(CHAR(1))
    id_card = Column(String(18), unique=True, nullable=False)
    license_no = Column(String(20), nullable=False)
    qualification_no = Column(String(30))
    phone = Column(String(15))
    hire_date = Column(Date)
    status = Column(Integer, default=1)
    operation_records = relationship("OperationRecord", back_populates="driver")

class VehicleDriver(Base):
    __tablename__ = "vehicle_driver"
    id = Column(BigInteger, primary_key=True, index=True)
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.id"))
    driver_id = Column(BigInteger, ForeignKey("driver.id"))
    assign_date = Column(Date)
    unassign_date = Column(Date, nullable=True)
    status = Column(Integer, default=1)

class OperationRecord(Base):
    __tablename__ = "operation_record"
    id = Column(BigInteger, primary_key=True, index=True)
    order_no = Column(String(30), unique=True, nullable=False)
    vehicle_id = Column(BigInteger, ForeignKey("vehicle.id"))
    driver_id = Column(BigInteger, ForeignKey("driver.id"))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    loaded_mileage = Column(Numeric(10, 2), nullable=False)
    empty_mileage = Column(Numeric(10, 2), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    pay_type = Column(String(10))
    create_time = Column(DateTime, default=datetime.utcnow)
    vehicle = relationship("Vehicle", back_populates="operation_records")
    driver = relationship("Driver", back_populates="operation_records")

class User(Base):
    __tablename__ = "sys_user"
    id = Column(BigInteger, primary_key=True, index=True)
    username = Column(String(30), unique=True, nullable=False)
    password_hash = Column(String(100), nullable=False)
    real_name = Column(String(30))
    role = Column(String(20), default="operator")
    status = Column(Integer, default=1)
    last_login = Column(DateTime)

class OperationLog(Base):
    __tablename__ = "operation_log"
    id = Column(BigInteger, primary_key=True, index=True)
    user_id = Column(BigInteger)
    operation = Column(String(100))
    method = Column(String(100))
    ip = Column(String(50))
    create_time = Column(DateTime, default=datetime.utcnow)