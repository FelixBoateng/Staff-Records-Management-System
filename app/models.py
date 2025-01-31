from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, DECIMAL, CheckConstraint, LargeBinary
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import validates, relationship, backref
from datetime import datetime
from enum import Enum
import uuid
from database.db_session import Base


# Enums
class MaritalStatus(Enum):
    Single = 'Single'
    Married = 'Married'
    Divorced = 'Divorced'
    Separated = 'Separated'
    Widowed = 'Widowed'
    Other = 'Other'

class Gender(Enum):
    Male = 'Male'
    Female = 'Female'
    Other = 'Other'

class Title(Enum):
    Prof = 'Prof.'
    Phd = 'PhD'
    Dr = 'Dr.'
    Mr = 'Mr.'
    Mrs = 'Mrs.'
    Ms = 'Ms.'
    Esq = 'Esq.'
    Hon = 'Hon.'
    Rev = 'Rev.'
    Msgr = 'Msgr.'
    Sr = 'Sr.'
    Other = 'Other'


# Calculate the range for the year constraint
current_year = datetime.now().year
min_year = current_year - 50


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, nullable=False, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)


class Centre(BaseModel):
    __tablename__ = "centre"

    location = Column(String, nullable=False)
    region = Column(String, nullable=True)
    directorates = relationship('Directorate', backref='centre', cascade='all, delete-orphan')


class Directorate(BaseModel):
    __tablename__ = "directorate"

    name = Column(String, nullable=False)
    centre_id = Column(UUID(as_uuid=True), ForeignKey('centre.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=False)
    employment_details = relationship('EmploymentDetail', backref='directorate', cascade='all, delete-orphan')


class Grade(BaseModel):
    __tablename__ = "grade"

    name = Column(String, nullable=False)
    min_sal = Column(DECIMAL(precision=10, scale=2), nullable=False,  default=0.00)
    max_sal = Column(DECIMAL(precision=10, scale=2), nullable=False,  default=0.00)
    employment_types = relationship('EmploymentType', backref='grade', cascade='all, delete-orphan')
    employment_details = relationship('EmploymentDetail', backref='grade', cascade='all, delete-orphan')


class EmploymentType(BaseModel):
    __tablename__ = "employment_type"

    name = Column(String, nullable=False)
    description = Column(String)
    grade_id = Column(UUID(as_uuid=True), ForeignKey('grade.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=False)
    employment_details = relationship('EmploymentDetail', backref='employment_type', cascade='all, delete-orphan')


class StaffCategory(BaseModel):
    __tablename__ = "staff_category"

    category = Column(String, nullable=False)
    employment_details = relationship('EmploymentDetail', backref='staff_category', cascade='all, delete-orphan')


class BioData(BaseModel):
    __tablename__ = "bio_data"

    title = Column(String, default=Title.Other.value, nullable=False)
    first_name = Column(String(100), nullable=False)
    other_names = Column(String(100), nullable=True)
    surname = Column(String(100), nullable=False)
    previous_name = Column(String, nullable=True)
    gender = Column(String, default=Gender.Other.value, nullable=False)
    date_of_birth = Column(Date, nullable=False)
    nationality = Column(String, nullable=False)
    hometown = Column(String, nullable=False)
    religion = Column(String, nullable=True)
    marital_status = Column(String, default=MaritalStatus.Other.value, nullable=False)
    residential_addr = Column(String, nullable=False)
    active_phone_number = Column(String, nullable=False)
    email = Column(String, nullable=False)
    ssnit_number = Column(String, nullable=False)
    ghana_card_number = Column(String, nullable=False)
    is_physically_challenged = Column(Boolean, nullable=False)
    disability = Column(String, nullable=True)
    image_col = Column(String, nullable=True)
    user = relationship('User', backref='bio_data', uselist=False, cascade='all, delete-orphan')
    employment_detail = relationship('EmploymentDetail', backref='bio_data', uselist=False, cascade='all, delete-orphan')
    bank_details = relationship('BankDetail', backref='bio_data', cascade='all, delete-orphan')
    academics = relationship('Academic', backref='bio_data', cascade='all, delete-orphan')
    professionals = relationship('Professional', backref='bio_data', cascade='all, delete-orphan')
    qualifications = relationship('Qualification', backref='bio_data', cascade='all, delete-orphan')
    employment_histories = relationship('EmploymentHistory', backref='bio_data', cascade='all, delete-orphan')
    family_infos = relationship('FamilyInfo', backref='bio_data', cascade='all, delete-orphan')
    emergency_contacts = relationship('EmergencyContact', backref='bio_data', cascade='all, delete-orphan')
    next_of_kins = relationship('NextOfKin', backref='bio_data', cascade='all, delete-orphan')
    declarations = relationship('Declaration', backref='bio_data', cascade='all, delete-orphan')


class User(BaseModel):
    __tablename__ = "users"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=True)
    hashed_password = Column(String, nullable=False)
    reset_pwd_token = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    role = Column(String, default="user")


class EmploymentDetail(BaseModel):
    __tablename__ = "employment_details"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    date_of_first_appointment = Column(Date, nullable=False)
    grade_on_first_appointment = Column(String, nullable=True)
    grade_on_current_appointment_id = Column(UUID(as_uuid=True), ForeignKey('grade.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    directorate_id = Column(UUID(as_uuid=True), ForeignKey('directorate.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    employee_number = Column(String, unique=True, index=True, nullable=False)
    employment_type_id = Column(UUID(as_uuid=True), ForeignKey('employment_type.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=False)
    staff_category_id = Column(UUID(as_uuid=True), ForeignKey('staff_category.id', ondelete='SET NULL', onupdate='CASCADE'), nullable=False)


class BankDetail(BaseModel):
    __tablename__ = "bank_details"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    bank_name = Column(String, nullable=False)
    bank_branch = Column(String, nullable=False)
    account_number = Column(String, unique=True, nullable=False)
    account_type = Column(String, nullable=False)
    account_status = Column(String, nullable=True)


class Academic(BaseModel):
    __tablename__ = "academics"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    institution = Column(String, nullable=False)
    year = Column(Date, CheckConstraint(f"year >= '{min_year}-01-01' AND year <= '{current_year}-12-31'"))
    programme = Column(String, nullable=True)
    qualification = Column(String, nullable=True)

    @validates('year')
    def validate_year(self, key, year):
        if year.year < min_year or year.year > current_year:
            raise ValueError(f"Year must be between {min_year} and {current_year}")
        return year


class Professional(BaseModel):
    __tablename__ = "professional"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    year = Column(Date, CheckConstraint(f"year >= '{min_year}-01-01' AND year <= '{current_year}-12-31'"))
    certification = Column(String, nullable=False)
    institution = Column(String, nullable=False)
    location = Column(String, nullable=True)

    @validates('year')
    def validate_year(self, key, year):
        if year.year < min_year or year.year > current_year:
            raise ValueError(f"Year must be between {min_year} and {current_year}")
        return year


class Qualification(BaseModel):
    __tablename__ = "qualification"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    academic_qualification_id = Column(UUID(as_uuid=True), ForeignKey('academics.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    professional_qualification_id = Column(UUID(as_uuid=True), ForeignKey('professional.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)


class EmploymentHistory(BaseModel):
    __tablename__ = "employment_history"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    date_employed = Column(Date, nullable=False)
    institution = Column(String, nullable=False)
    position = Column(String, nullable=False)
    end_date = Column(Date)


class FamilyInfo(BaseModel):
    __tablename__ = "family_info"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    name_of_spouse = Column(String, nullable=True)
    occupation = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    name_of_father_guardian = Column(String, nullable=True)
    fathers_occupation = Column(String, nullable=True)
    fathers_contact = Column(String, nullable=True)
    fathers_address = Column(String, nullable=True)
    name_of_mother_guardian = Column(String, nullable=True)
    mothers_occupation = Column(String, nullable=True)
    mothers_contact = Column(String, nullable=True)
    mothers_address = Column(String, nullable=True)
    children_name = Column(String, nullable=True)
    children_dob = Column(String, nullable=True)


class EmergencyContact(BaseModel):
    __tablename__ = "emergency_contacts"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    name = Column(String)
    phone_number = Column(String)
    address = Column(String)
    email = Column(String)


class NextOfKin(BaseModel):
    __tablename__ = "next_of_kin"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    title = Column(String, default=Title.Other.value, nullable=False)
    first_name = Column(String(100), nullable=False)
    other_name = Column(String(100))
    surname = Column(String(100), nullable=False)
    gender = Column(String, default=Gender.Other.value, nullable=False)
    relation = Column(String, nullable=False)
    address = Column(String)
    town = Column(String, nullable=False)
    region = Column(String, nullable=False)
    phone = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)


class Declaration(BaseModel):
    __tablename__ = "declaration"

    bio_row_id = Column(UUID(as_uuid=True), ForeignKey('bio_data.id', ondelete='CASCADE', onupdate='CASCADE'), nullable=False)
    status = Column(Boolean, default=False)
    reps_signature = Column(String, nullable=True)
    employees_signature = Column(String, nullable=True)
    declaration_date = Column(Date, default=func.now())

class Trademark(BaseModel):
    __tablename__ = "trademark"

    name = Column(String, unique=True, nullable=False)
    left_logo = Column(String, nullable=True)
    right_logo = Column(String, nullable=True)
    

