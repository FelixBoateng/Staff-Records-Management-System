import io
from database.db_session import  Base
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError
from sqlalchemy import inspect
import schemas
from fpdf import FPDF
from models import (Centre, Directorate, Grade, EmploymentType, StaffCategory, BioData, EmploymentDetail, 
                    BankDetail, Academic, Professional, Qualification, EmploymentHistory, FamilyInfo, EmergencyContact, NextOfKin, 
                    Declaration, StaffCategory,User, Trademark)


from PIL import Image,  UnidentifiedImageError
from io import BytesIO
from typing import TypeVar, Type, List, Dict
from fastapi import HTTPException, logger, status, UploadFile
from PIL import Image, UnidentifiedImageError
from datetime import datetime

from sqlalchemy.exc import SQLAlchemyError
from pydantic import EmailStr

import tempfile

from typing import Type, TypeVar, Generic, List, Optional, Any, Union
from pydantic import BaseModel
from sqlalchemy.orm import Session
from fastapi.encoders import jsonable_encoder
import uuid
from sqlalchemy import  String, Text
from sqlalchemy import or_ 
import os
from pathlib import Path
from uuid import UUID
import shutil
import base64
from sqlalchemy.types import String, Text, UUID
from sqlalchemy.dialects.postgresql import UUID as PostgreSQL_UUID

from uuid import UUID as UUIDType
from sqlalchemy.types import String, Text, UUID, DateTime, Boolean, Date

from tempfile import NamedTemporaryFile, TemporaryDirectory
from PIL import ImageEnhance
import json
import re
from sqlalchemy.orm import class_mapper


from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password='password'):
    return pwd_context.hash(password)


ModelType = TypeVar("ModelType", bound=Base)
CreateSchemaType = TypeVar("CreateSchemaType", bound=BaseModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=BaseModel)



UPLOAD_DIR = 'uploads/images'
PASSPORT_SIZE = (100, 100)

def save_and_resize_image(file: UploadFile, filename: str) -> str:
    try:
        # Check if the file is an image
        image = Image.open(file.file)
        file.file.seek(0)  # Reset file pointer after reading for validation
    except UnidentifiedImageError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is not a valid image")

    if not os.path.exists(UPLOAD_DIR):
        os.makedirs(UPLOAD_DIR)
    filepath = os.path.join(UPLOAD_DIR, filename)

    with open(filepath, 'wb') as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Resize image
    image = Image.open(filepath)
    image = image.resize(PASSPORT_SIZE)

     # Convert image to RGB mode if it is in RGBA mode
    if image.mode == 'RGBA':
        image = image.convert('RGB')

    image.save(filepath)

    return filepath

def image_to_base64(filepath: str) -> str:
    with open(filepath, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode('utf-8')
    
    return f"data:image/png;base64,{encoded_string}"

def _image_to_base64(filepath: bytes) -> bytes:
    encoded_string = base64.b64encode(filepath).decode('utf-8')
    return f"data:image/png;base64,{encoded_string}"

def get_user(db: Session, user_id: uuid.UUID):
    return db.query(User).filter(User.id == user_id).first()

def update_user(db: Session, user_id: uuid.UUID, user_update: schemas.UserUpdate):
    db_user = get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = user_update.dict(exclude_unset=True)
    
    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    for key, value in update_data.items():
        setattr(db_user, key, value)

    db.commit()
    db.refresh(db_user)
    return db_user

def get_user_by_username(db: Session, username: str):
    return db.query(User).filter(User.username == username).first()

def get_user_by_email(db: Session, email: str):
    return db.query(User).filter(User.email == email).first()

def get_user_data(db: Session, user_id: uuid.UUID):
    user = get_user(db, user_id)
    bio = db.query(BioData, EmploymentDetail).filter(
        BioData.id == user.bio_row_id, 
        EmploymentDetail.bio_row_id==user.bio_row_id).first()
   
    data = {
        "Full_Name":bio["first_name"] + bio["surname"],
        "Email": bio["email"],
        "Phone_Number": bio["active_phone_number"],
        "Employment_Type": bio["employment_type_id"],
        "Staff_Category":bio["staff_category_id"],
        "Role":user.role
        }
    return data



def get_users(db: Session, skip: int = 0, limit: int = 100) -> List[User]:
    objs = db.query(User).offset(skip).limit(limit).all()
    return objs

def create_user(db: Session, user: schemas.UserCreate):
# Check if username exists
    if get_user_by_username(db, user.username):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Forbidden: Username '{user.username}' already exists.")

    # Create user with hashed password
    hash_password = get_password_hash(user.hashed_password)
    db_user = User(
        bio_row_id=user.bio_row_id,
        username=user.username,
        email = user.email,
        hashed_password=hash_password,
        role=user.role,
        is_active=user.is_active
    )

    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user




#----------------------------------------------

def is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except ValueError:
        return False



def custom_jsonable_encoder(record):
    try:
        if isinstance(record, dict):
            return {k: custom_jsonable_encoder(v) for k, v in record.items()}
        elif isinstance(record, list):
            return [custom_jsonable_encoder(v) for v in record]
        elif isinstance(record, uuid.UUID):
            return str(record)
        elif hasattr(record, "__dict__"):
            # Prevent recursion by excluding SQLAlchemy attributes
            model_dict = {k: v for k, v in record.__dict__.items() if not k.startswith('_sa')}
            return custom_jsonable_encoder(model_dict)
        return jsonable_encoder(record)
    except Exception as e:
        print(f"Error in custom_jsonable_encoder: {e}")
        raise e

def validate_input(input_string: str) -> bool:
    # Basic SQL injection prevention
    forbidden_patterns = [
        r"(?i)\b(select|insert|update|delete|drop|truncate|exec|execute|union|create|alter|rename|revoke|grant|replace|shutdown|backup|restore)\b",
        r"(--)|(/\*)|(\*/)|(;)"
    ]
    for pattern in forbidden_patterns:
        if re.search(pattern, input_string):
            return False
    return True

def search_related_models(db: Session, related_model: Type[Any], search_terms: List[str]) -> List[Dict[str, Any]]:
    conditions = []
    for column in inspect(related_model).columns:
        if isinstance(column.type, (String, Text)):
            for term in search_terms:
                conditions.append(getattr(related_model, column.name).ilike(f"%{term}%"))
    if conditions:
        related_query_results = db.query(related_model).options(joinedload('*')).filter(or_(*conditions)).all()
        return [custom_jsonable_encoder(record) for record in related_query_results]
    return []




def search_all(db: Session, search_string: str, models: List[Type[Any]], current_user: User) -> Dict[str, List[Dict[str, Any]]]:
    
    if not validate_input(search_string):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input detected")
    
    results = {}
    search_terms = search_string.lower().split()
    # Sanitize and validate input
    search_terms = re.sub(r'[^\w\s]', '', search_string.lower().strip())  # Remove special characters

    try:
        for model in models:
            query = db.query(model)
            conditions = []
            for column in inspect(model).columns:
                if isinstance(column.type, (String, Text)):
                    for term in search_terms:
                        conditions.append(getattr(model, column.name).ilike(f"%{term}%"))
                elif isinstance(column.type, (PostgreSQL_UUID, uuid.UUID)):
                    if is_valid_uuid(search_string):
                        conditions.append(getattr(model, column.name) == uuid.UUID(search_string))
                elif isinstance(column.type, (DateTime, Boolean, Date)):
                    pass  # Skip these types for search
                else:
                    continue  # Skip any other types
            if conditions:
                query_results = query.filter(or_(*conditions)).all()
                if query_results:
                    if current_user.role == "admin":
                        model_results = [custom_jsonable_encoder(record) for record in query_results]
                    else:
                        model_results = []
                        for record in query_results:
                            if record.id == current_user.bio_row_id:
                                model_results.append(custom_jsonable_encoder(record))
                            else:
                                basic_details = {
                                    'Name': getattr(record, 'name', None),
                                    'Staff Category': getattr(record, 'staff_category', None),
                                    'Employment Type': getattr(record, 'employment_type', None),
                                    'Qualification': getattr(record, 'qualification', None),
                                    'Image': getattr(record, 'image_col', None)
                                }
                                model_results.append(basic_details)
                    if model_results:
                        results[model.__name__] = model_results
        return results
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Error in search_all: {str(e)}")





# def search_all(db: Session, search_string: str, models: List[Type[Any]], current_user: User) -> Dict[str, List[Dict[str, Any]]]:
#     if not validate_input(search_string):
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid input detected")

#     results = {}
#     search_terms = search_string.lower().split()

#     try:
#         for model in models:
#             query = db.query(model)
#             conditions = []
#             for column in inspect(model).columns:
#                 if isinstance(column.type, (String, Text)):
#                     for term in search_terms:
#                         conditions.append(getattr(model, column.name).ilike(f"%{term}%"))
#                 elif isinstance(column.type, (PostgreSQL_UUID, uuid.UUID)):
#                     if is_valid_uuid(search_string):
#                         conditions.append(getattr(model, column.name) == uuid.UUID(search_string))
#                 elif isinstance(column.type, (EmailStr)):
#                     for term in search_terms:
#                         conditions.append(getattr(model, column.name) == term)
#                 elif isinstance(column.type, (DateTime, Boolean, Date)):
#                     pass  # Skip these types for search
#                 else:
#                     continue  # Skip any other types
#             if conditions:
#                 query_results = query.options(joinedload('*')).filter(or_(*conditions)).all()
#                 model_results = [custom_jsonable_encoder(record) for record in query_results]

#                 if model_results:
#                     results[model.__name__] = model_results
#                 # Query related models
#                 # for result in model_results:
#                 #     for related_field in inspect(model).relationships:
#                 #         related_model = related_field.mapper.class_
#                 #         related_results = search_related_models(db, related_model, search_terms)
#                 #         if related_results:
#                 #             result[related_field.key] = related_results

#                 # results[model.__name__] = model_results
#         return results
#     except SQLAlchemyError as e:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

# Example usage




#--------------------------------
# def search_all(db: Session, search_string: str, models: List[Type[ModelType]]) -> Dict[str, List[Dict[str, Any]]]:
#     results = {}
#     try:
#         for model in models:
#             query = db.query(model)
#             conditions = []
#             for column in inspect(model).columns:
#                 if isinstance(column.type, (String, Text)):
#                     conditions.append(getattr(model, column.name).ilike(f"%{search_string}%"))
#             if conditions:
#                 query_results = query.filter(or_(*conditions)).all()
#                 results[model.__name__] = [jsonable_encoder(record) for record in query_results]
#         return results
#     except Exception as e:
#         db.rollback()
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


class TCRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        obj = db.query(self.model).filter(self.model.id == id).first()
        if obj and obj.left_logo:
            obj.left_logo = image_to_base64(obj.left_logo)
        return obj
    
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        objs = db.query(self.model).offset(skip).limit(limit).all()
        
        for obj in objs:
            if obj.left_logo:
                obj.left_logo = image_to_base64(obj.left_logo)
            if obj.right_logo:
                obj.right_logo = image_to_base64(obj.right_logo)
        return objs
    
    def get_by_field(self, db: Session, field: str, value: Any) -> Optional[ModelType]:
        obj = db.query(self.model).filter(getattr(self.model, field) == value).first()
        if obj and obj.left_logo:
            obj.left_logo = image_to_base64(obj.left_logo)
        return obj

    def create(self, db: Session, obj_in: CreateSchemaType, file: UploadFile = None, file2: UploadFile = None) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in)
        if file:
            filename = f"{obj_in.name}_left.jpg" #f"{uuid.uuid4()}.jpg" 
            filepath = save_and_resize_image(file, filename)
            obj_in_data['left_logo'] = filepath
        if file2:
            filename2 = f"{obj_in.name}_right.jpg"  #f"{uuid.uuid4()}.jpg"
            filepath2 = save_and_resize_image(file2, filename2)
            obj_in_data['right_logo'] = filepath2

        try:
            db_obj = self.model(**obj_in_data)
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            # if db_obj.left_logo:
            #     db_obj.left_logo = image_to_base64(db_obj.left_logo)
            # if db_obj.right_logo:
            #     db_obj.right_logo = image_to_base64(db_obj.right_logo)
            return db_obj
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    def update(self, db: Session, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]], file: UploadFile = None, file2: UploadFile = None) -> ModelType:
        obj_data = jsonable_encoder(db_obj)
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)

        if file:
            filename = f"{obj_in.name}_left.jpg"  #f"{uuid.uuid4()}.jpg"
            filepath = save_and_resize_image(file, filename)
            update_data['left_logo'] = filepath
        if file2:
            filename2 = f"{obj_in.name}_left.jpg"  #f"{uuid.uuid4()}.jpg"
            filepath2 = save_and_resize_image(file2, filename2)
            update_data['right_logo'] = filepath2

        try:
            for field in obj_data:
                if field in update_data:
                    setattr(db_obj, field, update_data[field])
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            # if db_obj.left_logo:
            #     db_obj.left_logo = image_to_base64(db_obj.left_logo)
            # if db_obj.right_logo:
            #     db_obj.right_logo = image_to_base64(db_obj.right_logo)
            return db_obj
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        objs = db.query(self.model).offset(skip).limit(limit).all()
        
        for obj in objs:
            if obj.left_logo and obj.left_logo != '' and obj.left_logo != None:
                obj.left_logo = image_to_base64(obj.left_logo)
            
            if obj.right_logo and obj.right_logo != '' and obj.right_logo != None:
                obj.right_logo = image_to_base64(obj.right_logo)
        return objs

    # Define a function to delete the logo file if it exists
    def delete_logo_file(self, name: str, logo_type: str) -> bool:
        """
        Delete the logo file if it exists on the disk.

        Args:
        - name (str): The base name used to construct the file path.
        - logo_type (str): Either 'left' or 'right' to indicate which logo to delete.

        Returns:
        - bool: True if the file was successfully deleted, False otherwise.
        """
        # Construct the expected file path based on 'name' and 'logo_type'
        filename = f"{name}_{logo_type}.jpg"
        filepath = os.path.join("./uploads/images/", filename)
        
        if os.path.isfile(filepath):
            try:
                os.remove(filepath)  # Delete the file
                return True
            except OSError as e:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Error deleting file {filepath}: {str(e)}"
                )
        return False  # File doesn't exist, so nothing to delete
                    

    def delete_trademark(self, db: Session, trademark_id: UUID) -> str:
        # Retrieve the trademark row from the database by its id
        trademark = db.query(self.model).filter(self.model.id == trademark_id).first()
        
        # If no row is found, raise an HTTP exception
        if not trademark:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trademark with id {trademark_id} not found."
            )
        
        # Attempt to delete both logos, prioritizing the left logo
        errors = []

        # Handle left logo
        if trademark.left_logo:
            if not self.delete_logo_file(trademark.name, 'left'):
                errors.append(f"Error eliminating left logo: {trademark.left_logo}")
        
        # Handle right logo
        if trademark.right_logo:
            if not self.delete_logo_file(trademark.name, 'right'):
                errors.append(f"Error eliminating right logo: {trademark.right_logo}")
        
        # Delete the trademark row from the database
        db.delete(trademark)
        db.commit()

        # If any errors occurred during file deletion, return them
        if errors:
            return ", ".join(errors)

        return f"Trademark with id {trademark_id} has been deleted successfully."



trademark = TCRUDBase(Trademark)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    def process_image(self, image_file: UploadFile) -> str:
        image = Image.open(image_file.file)
        image = image.resize((100, 100))
        byte_arr = io.BytesIO()
        image.save(byte_arr, format='JPEG')
        return base64.b64encode(byte_arr.getvalue()).decode()

    def handle_image_fields(self, data: Dict[str, Any], files: Dict[str, Any]) -> Dict[str, Any]:
        if not files:
            return data

        if isinstance(files, UploadFile):
            files = {"file": files}

        for key, file in files.items():
            if file:
                if self.model == BioData and key == 'image_col':
                    filename = f"{uuid.uuid4()}.jpg"
                    filepath = save_and_resize_image(file, filename)
                    data[key] = filepath
                elif self.model == Declaration and key in ['reps_signature', 'employees_signature']:
                    data[key] = self.process_image(file)
        
        return data

    def get(self, db: Session, id: Any) -> Optional[ModelType]:
        obj = db.query(self.model).filter(self.model.id == id).first()
       
            
        return obj

    def get_by_field(self, db: Session, field: str, value: Any) -> Optional[ModelType]:
        obj = db.query(self.model).filter(getattr(self.model, field) == value).first()
        if obj and obj.image_col:
            obj.image_col = image_to_base64(obj.image_col)
        return obj

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        objs = db.query(self.model).offset(skip).limit(limit).all()
        
        for obj in objs:
            if obj.image_col:
                obj.image_col = image_to_base64(obj.image_col)
        return objs
    
    

    def create(self, db: Session, obj_in: CreateSchemaType, files: Dict[str, Any] = None, **kw) -> ModelType:
        obj_in_data = jsonable_encoder(obj_in, **kw)
        obj_in_data = self.handle_image_fields(obj_in_data, files)

        try:
            for field in inspect(self.model).columns:
                if field.unique or field.index:
                    value = obj_in_data.get(field.name)
                    if value and db.query(self.model).filter(getattr(self.model, field.name) == value).first():
                        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field.name} '{value}' already exists.")
            
            db_obj = self.model(**obj_in_data)  # type: ignore
            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except:
            db.rollback()
            raise

    def update(self, db: Session, db_obj: ModelType, obj_in: Union[UpdateSchemaType, Dict[str, Any]], files: Dict[str, Any] = None) -> ModelType:
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        update_data = self.handle_image_fields(update_data, files)

        try:
            for field in inspect(self.model).columns:
                if field.unique or field.index:
                    new_value = update_data.get(field.name)
                    if new_value:
                        existing_obj = db.query(self.model).filter(getattr(self.model, field.name) == new_value).first()
                        if existing_obj and existing_obj.id != db_obj.id:
                            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{field.name} '{new_value}' belongs to another record.")
            
            for field, value in update_data.items():
                setattr(db_obj, field, value)

            db.add(db_obj)
            db.commit()
            db.refresh(db_obj)
            return db_obj
        except IntegrityError as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unique constraint failed.")
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))



    def remove(self, db: Session, id: Union[uuid.UUID, Dict[str, Any]]) -> ModelType:
        try:
            if isinstance(id, uuid.UUID):
                obj = db.query(self.model).filter(self.model.id == id).first()
            elif isinstance(id, dict):
                obj = None
                for field, value in id.items():
                    if inspect(self.model).columns[field].unique or inspect(self.model).columns[field].index:
                        obj = db.query(self.model).filter(getattr(self.model, field) == value).first()
                        if obj:
                            break

            if not obj:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Item not found.")

            # # Check referential integrity
            for relationship in inspect(self.model).relationships:
                if db.query(relationship.mapper.class_).filter(getattr(relationship.mapper.class_, relationship.back_populates) == obj).count() > 0:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot delete {self.model.__name__} because it is referenced by other records.")

            db.delete(obj)
            db.commit()
            return obj
        except:
            db.rollback()
            raise
    
    
   



#BioData
class CRUDBioData(CRUDBase[schemas.BioData, schemas.BioDataCreate, schemas.BioDataUpdate]):
    pass

bio_data = CRUDBioData(BioData)


#user
class CRUDUser(CRUDBase[schemas.User, schemas.UserCreate, schemas.UserUpdate]):
    pass

user = CRUDUser(User)





#declaration
class CRUDDeclaration(CRUDBase[schemas.Declaration, schemas.DeclarationCreate, schemas.DeclarationUpdate]):
    def get_multi_declarations(self, db: Session, skip: int = 0, limit: int = 100) -> List[ModelType]:
        objs = db.query(self.model).offset(skip).limit(limit).all()
        
        for obj in objs:

            if obj.reps_signature and obj.reps_signature != 'base64_representation_of_reps_signature_image' and obj.reps_signature != '' and obj.reps_signature != None:
                obj.reps_signature = image_to_base64(obj.reps_signature)
            
            if obj.employees_signature and obj.employees_signature != 'base64_representation_of_employees_signature_image' and obj.employees_signature != '' and obj.employees_signature != None:
                obj.employees_signature = image_to_base64(obj.employees_signature)
        return objs
    def create(self, db: Session, obj_in: schemas.DeclarationCreate, files: Dict[str, Any]) -> Declaration:
        obj_in_data = obj_in.dict()
        if 'reps_signature' in files and files['reps_signature']:
            obj_in_data['reps_signature'] = self.process_image(files['reps_signature'])
        if 'employees_signature' in files and files['employees_signature']:
            obj_in_data['employees_signature'] = self.process_image(files['employees_signature'])
        
        return super().create(db, schemas.DeclarationCreate(**obj_in_data))

    def update(self, db: Session, db_obj: Declaration, obj_in: Union[schemas.DeclarationUpdate, Dict[str, Any]], files: Dict[str, Any]) -> Declaration:
        update_data = obj_in.dict(exclude_unset=True)
        if 'reps_signature' in files and files['reps_signature']:
            update_data['reps_signature'] = self.process_image(files['reps_signature'])
        if 'employees_signature' in files and files['employees_signature']:
            update_data['employees_signature'] = self.process_image(files['employees_signature'])
        
        return super().update(db, db_obj, update_data, files=files)

    def process_image(self, image_file: Any) -> str:
        image = Image.open(io.BytesIO(image_file))
        image = image.resize((100, 100))
        byte_arr = io.BytesIO()
        image.save(byte_arr, format='JPEG')
        return base64.b64encode(byte_arr.getvalue()).decode()

    def remove(self, db: Session, id: UUID, force_delete: bool = False) -> Declaration:
        declaration = self.get(db, id)
        if not declaration:
            raise HTTPException(status_code=404, detail="Declaration not found")
        
        bio_data = db.query(BioData).filter(BioData.id == declaration.bio_row_id).first()
        if not bio_data:
            raise HTTPException(status_code=404, detail="BioData not found")
        
        if not force_delete:
            raise HTTPException(status_code=400, detail="Note that this action will delete all related data and is irreversible."+
                                "Are you sure you want to delete all related data? Set force_delete=True to confirm.")    
        
        self._delete_related_data(db, bio_data.id)
        db.delete(declaration)
        db.commit()
        
        return declaration

    def _delete_related_data(self, db: Session, bio_data_id: UUID):
        related_models = [
            EmploymentDetail, BankDetail, Academic, Professional, Qualification, EmploymentHistory, 
            FamilyInfo, EmergencyContact, NextOfKin, Declaration, User
        ]

        try:
            for model in related_models:
                db.query(model).filter(model.bio_row_id == bio_data_id).delete()
        
            db.query(BioData).filter(BioData.id == bio_data_id).delete()
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Integrity violation may be the cause. \n{e}")

declaration = CRUDDeclaration(Declaration)




#------------------------------------------------------------------------------

def generate_pdf_for_bio_data(bio_data, trademark, declarations, academics, professionals, employment_histories, emergency_contacts, next_of_kin, file_path):
    try:
        # Create the base directory if it doesn't exist
        base_dir = 'downloads/documents/'
        os.makedirs(base_dir, exist_ok=True)

        # Use bio_data_id as the file name
        file_name = f"bio_data_{bio_data.id}.pdf"
        file_path = os.path.join(base_dir, file_name)

        # Create a temporary directory
        with TemporaryDirectory() as tmpdirname:
            pdf = FPDF()
            pdf.add_page()

            # Add organization logo
            if trademark.left_logo:
                pdf.image(trademark.left_logo, x=95, y=10, w=20, h=20)


            # Add title
            pdf.set_font("Arial", size=14)
            pdf.ln(20)  # Adjust space after the logo
            pdf.cell(200, 10, txt=f"{trademark.name}".upper(), ln=True, align='C')

            pdf.set_font("Arial", size=12)
            pdf.ln()  # Adjust space after the logo
            pdf.cell(200, 10, txt="Personal Record Form", ln=True, align='C')

            # Add bio data image (passport size) at the top extreme right corner
            if bio_data.image_col:
                bio_image_path = os.path.join(tmpdirname, 'bio_image.jpg')
                with Image.open(bio_data.image_col) as img:
                    img.resize((100, 100), Image.LANCZOS).save(bio_image_path)  # Correct resizing method
                pdf.image(bio_image_path, x=180, y=10, w=20, h=20)

            # Add tags and bio data information
            pdf.set_font("Arial", size=10)
            pdf.ln(10)
            pdf.cell(200, 10, txt="A. Employee Bio-Data", ln=True, align='L')
            bio_info = [
                f"Title: {bio_data.title}",
                f"First Name: {bio_data.first_name}",
                f"Other Names: {bio_data.other_names or ''}",
                f"Surname: {bio_data.surname}",
                f"Previous Name: {bio_data.previous_name or ''}",
                f"Gender: {bio_data.gender}",
                f"Date of Birth: {bio_data.date_of_birth}",
                f"Nationality: {bio_data.nationality}",
                f"Hometown: {bio_data.hometown}",
                f"Religion: {bio_data.religion or ''}",
                f"Marital Status: {bio_data.marital_status}",
                f"Residential Address: {bio_data.residential_addr}",
                f"Active Phone Number: {bio_data.active_phone_number}",
                f"Email: {bio_data.email}",
                f"SSNIT Number: {bio_data.ssnit_number}",
                f"Ghana Card Number: {bio_data.ghana_card_number}",
                f"Physically Challenged: {'Yes' if bio_data.is_physically_challenged else 'No'}",
                f"Disability: {bio_data.disability or ''}"
            ]

            for info in bio_info:
                pdf.cell(200, 10, txt=info, ln=True, align='L')

            # Add employment details
            pdf.ln(10)
            pdf.cell(200, 10, txt="B. Employment Details", ln=True, align='L')
            employment_info = [
                f"Date of First Appointment: {bio_data.employment_detail.date_of_first_appointment}",
                f"Grade on First Appointment: {bio_data.employment_detail.grade_on_first_appointment}",
                f"Grade on Current Appointment: {bio_data.employment_detail.grade_on_current_appointment_id}",
                f"Directorate: {bio_data.employment_detail.directorate_id}",
                f"Employee Number: {bio_data.employment_detail.employee_number}",
                f"Employment Type: {bio_data.employment_detail.employment_type_id}",
                f"Staff Category: {bio_data.employment_detail.staff_category_id}"
            ]

            for emp_info in employment_info:
                pdf.cell(200, 10, txt=emp_info, ln=True, align='L')

            # Add bank details
            pdf.ln(10)
            pdf.cell(200, 10, txt="C. Bank Details", ln=True, align='L')
            for bank_detail in bio_data.bank_details:
                bank_info = [
                    f"Bank Name: {bank_detail.bank_name}",
                    f"Bank Branch: {bank_detail.bank_branch}",
                    f"Account Number: {bank_detail.account_number}",
                    f"Account Type: {bank_detail.account_type}",
                    f"Account Status: {bank_detail.account_status or ''}"
                ]
                for info in bank_info:
                    pdf.cell(200, 10, txt=info, ln=True, align='L')

            # Add academic details in tabular form
            pdf.ln(10)
            pdf.cell(200, 10, txt="D. Academic Details", ln=True, align='L')
            pdf.cell(60, 10, txt="Institution", border=1, align='C')
            pdf.cell(30, 10, txt="Year", border=1, align='C')
            pdf.cell(50, 10, txt="Programme", border=1, align='C')
            pdf.cell(50, 10, txt="Qualification", border=1, align='C')
            pdf.ln()
            for academic in academics:
                pdf.cell(60, 10, txt=academic.institution, border=1, align='C')
                pdf.cell(30, 10, txt=str(academic.year), border=1, align='C')
                pdf.cell(50, 10, txt=academic.programme or '', border=1, align='C')
                pdf.cell(50, 10, txt=academic.qualification or '', border=1, align='C')
                pdf.ln()

            # Add professional details in tabular form
            pdf.ln(10)
            pdf.cell(200, 10, txt="E. Professional Details", ln=True, align='L')
            pdf.cell(60, 10, txt="Institution", border=1, align='C')
            pdf.cell(30, 10, txt="Year", border=1, align='C')
            pdf.cell(50, 10, txt="Certification", border=1, align='C')
            pdf.cell(50, 10, txt="Location", border=1, align='C')
            pdf.ln()
            for professional in professionals:
                pdf.cell(60, 10, txt=professional.institution, border=1, align='C')
                pdf.cell(30, 10, txt=str(professional.year), border=1, align='C')
                pdf.cell(50, 10, txt=professional.certification, border=1, align='C')
                pdf.cell(50, 10, txt=professional.location or '', border=1, align='C')
                pdf.ln()

            # Add employment history in tabular form
            pdf.ln(10)
            pdf.cell(200, 10, txt="G. Employment History", ln=True, align='L')
            pdf.cell(60, 10, txt="Institution", border=1, align='C')
            pdf.cell(30, 10, txt="Date Employed", border=1, align='C')
            pdf.cell(50, 10, txt="Position", border=1, align='C')
            pdf.cell(50, 10, txt="End Date", border=1, align='C')
            pdf.ln()
            for history in employment_histories:
                pdf.cell(60, 10, txt=history.institution, border=1, align='C')
                pdf.cell(30, 10, txt=str(history.date_employed), border=1, align='C')
                pdf.cell(50, 10, txt=history.position, border=1, align='C')
                pdf.cell(50, 10, txt=str(history.end_date) if history.end_date else '', border=1, align='C')
                pdf.ln()

            # Add emergency contacts
            pdf.ln(10)
            pdf.cell(200, 10, txt="H. Emergency Contacts", ln=True, align='L')
            for contact in emergency_contacts:
                emergency_info = [
                    f"Name: {contact.name}",
                    f"Phone Number: {contact.phone_number}",
                    f"Address: {contact.address}",
                    f"Email: {contact.email}"
                ]
                for info in emergency_info:
                    pdf.cell(200, 10, txt=info, ln=True, align='L')

            # Add next of kin
            pdf.ln(10)
            pdf.cell(200, 10, txt="I. Next of Kin", ln=True, align='L')
            for kin in next_of_kin:
                kin_info = [
                    f"Title: {kin.title}",
                    f"First Name: {kin.first_name}",
                    f"Other Name: {kin.other_name or ''}",
                    f"Surname: {kin.surname}",
                    f"Gender: {kin.gender}",
                    f"Relation: {kin.relation}",
                    f"Address: {kin.address or ''}",
                    f"Town: {kin.town}",
                    f"Region: {kin.region}",
                    f"Phone: {kin.phone}",
                    f"Email: {kin.email}"
                ]
                for info in kin_info:
                    pdf.cell(200, 10, txt=info, ln=True, align='L')


            # Add declarations signatures and dates
            if declarations:
                pdf.ln(10)
                pdf.cell(200, 10, txt="F. Declarations", ln=True, align='L')

                signatures_dir = 'downloads/signatures'
                os.makedirs(signatures_dir, exist_ok=True)

                for declaration in declarations:
                    if declaration.reps_signature:
                        reps_signature_img_path = os.path.join(signatures_dir, 'reps_signature.png')
                        with Image.open(BytesIO(base64.b64decode(declaration.reps_signature))) as img:
                            img.resize((100, 100), Image.LANCZOS).save(reps_signature_img_path)
                        
                        pdf.image(reps_signature_img_path, x=10, y=pdf.get_y(), w=40, h=20)
                    
                    

                    if declaration.employees_signature:
                        employees_signature_img_path = os.path.join(signatures_dir, 'employees_signature.png')
                        with Image.open(BytesIO(base64.b64decode(declaration.employees_signature))) as img:
                            img.resize((100, 100), Image.LANCZOS).save(employees_signature_img_path)
                     
                        pdf.image(employees_signature_img_path, x=165, y=pdf.get_y(), w=40, h=20)
                    
                    pdf.ln(20)
                    pdf.cell(100, 10, txt="Rep's Signature", ln=False, align='L')
                    pdf.cell(90, 10, txt="Employee's Signature", ln=False, align='R')
                    pdf.ln(10)
                    pdf.cell(165, 10, txt=f"Declaration Date: {declaration.declaration_date.strftime('%d-%b-%Y')}", ln=False, align='C')  
                    
                    pdf.ln(6)
                    pdf.cell(165, 10, txt="---------- END ----------", ln=False, align='C')

                    #pdf.ln(10)
                    
                    #pdf.ln(10)
                    #pdf.cell(200, 10, txt=f"Declaration Date: {declaration.declaration_date}", ln=True, align='R')

            # Add page numbers
            # pdf.set_auto_page_break(auto=True, margin=15)
            # pdf_alias_nb = pdf.alias_nb_pages()
            # total_pages = pdf.page_no()
            # for i in range(1, total_pages + 1):
            #     pdf.page = i
            #     pdf.set_y(-15)
            #     pdf.set_font('Arial', 'I', 8)
            #     pdf.cell(0, 10, f'Page {i} of {total_pages}', 0, 0, 'R')

        # Save the PDF
        pdf.output(file_path)
        return file_path

    except Exception as e:
        print(f"An error occurred: {e}")
        return None















#------------------------------------------------------------------------------
# def generate_pdf_for_bio_data(bio_data, trademark, declarations, academics, professionals, file_path):
#     # Create temporary directory
#     with tempfile.TemporaryDirectory() as tmpdirname:
#         pdf = FPDF()
#         pdf.add_page()

#         # Add organization logo
#         if trademark.left_logo:
#             pdf.image(trademark.left_logo, x=95, y=10, w=20, h=20)

#         # Add title
#         pdf.set_font("Arial", size=12)
#         pdf.ln(30)  # Adjust space after the logo
#         pdf.cell(200, 10, txt="Personal Record Form", ln=True, align='C')

#         # Add bio data image (passport size) at the top extreme right corner
#         if bio_data.image_col:
#             bio_image_path = os.path.join(tmpdirname, 'bio_image.jpg')
#             Image.open(bio_data.image_col).resize((20, 20)).save(bio_image_path)
#             pdf.image(bio_image_path, x=180, y=10, w=20, h=20)

#         # Add tags and bio data information
#         pdf.set_font("Arial", size=10)
#         pdf.ln(10)
#         pdf.cell(200, 10, txt="A. Employee Bio-Data", ln=True, align='L')
#         bio_info = [
#             f"Title: {bio_data.title}",
#             f"First Name: {bio_data.first_name}",
#             f"Other Names: {bio_data.other_names or ''}",
#             f"Surname: {bio_data.surname}",
#             f"Previous Name: {bio_data.previous_name or ''}",
#             f"Gender: {bio_data.gender}",
#             f"Date of Birth: {bio_data.date_of_birth}",
#             f"Nationality: {bio_data.nationality}",
#             f"Hometown: {bio_data.hometown}",
#             f"Religion: {bio_data.religion or ''}",
#             f"Marital Status: {bio_data.marital_status}",
#             f"Residential Address: {bio_data.residential_addr}",
#             f"Active Phone Number: {bio_data.active_phone_number}",
#             f"Email: {bio_data.email}",
#             f"SSNIT Number: {bio_data.ssnit_number}",
#             f"Ghana Card Number: {bio_data.ghana_card_number}",
#             f"Physically Challenged: {'Yes' if bio_data.is_physically_challenged else 'No'}",
#             f"Disability: {bio_data.disability or ''}"
#         ]

#         for info in bio_info:
#             pdf.cell(200, 10, txt=info, ln=True, align='L')

#         # Add employment details
#         pdf.ln(10)
#         pdf.cell(200, 10, txt="B. Employment Details", ln=True, align='L')
#         employment_info = [
#             f"Date of First Appointment: {bio_data.employment_detail.date_of_first_appointment}",
#             f"Grade on First Appointment: {bio_data.employment_detail.grade_on_first_appointment}",
#             f"Grade on Current Appointment: {bio_data.employment_detail.grade_on_current_appointment_id}",
#             f"Directorate: {bio_data.employment_detail.directorate_id}",
#             f"Employee Number: {bio_data.employment_detail.employee_number}",
#             f"Employment Type: {bio_data.employment_detail.employment_type_id}",
#             f"Staff Category: {bio_data.employment_detail.staff_category_id}"
#         ]

#         for info in employment_info:
#             pdf.cell(200, 10, txt=info, ln=True, align='L')

#         # Add bank details
#         pdf.ln(10)
#         pdf.cell(200, 10, txt="C. Bank Details", ln=True, align='L')
#         for bank_detail in bio_data.bank_details:
#             bank_info = [
#                 f"Bank Name: {bank_detail.bank_name}",
#                 f"Bank Branch: {bank_detail.bank_branch}",
#                 f"Account Number: {bank_detail.account_number}",
#                 f"Account Type: {bank_detail.account_type}",
#                 f"Account Status: {bank_detail.account_status or ''}"
#             ]
#             for info in bank_info:
#                 pdf.cell(200, 10, txt=info, ln=True, align='L')

#         # Add academic details in tabular form
#         pdf.ln(10)
#         pdf.cell(200, 10, txt="D. Academic Details", ln=True, align='L')
#         pdf.cell(60, 10, txt="Institution", border=1, align='C')
#         pdf.cell(30, 10, txt="Year", border=1, align='C')
#         pdf.cell(50, 10, txt="Programme", border=1, align='C')
#         pdf.cell(50, 10, txt="Qualification", border=1, align='C')
#         pdf.ln()
#         for academic in academics:
#             pdf.cell(60, 10, txt=academic.institution, border=1, align='C')
#             pdf.cell(30, 10, txt=str(academic.year), border=1, align='C')
#             pdf.cell(50, 10, txt=academic.programme or '', border=1, align='C')
#             pdf.cell(50, 10, txt=academic.qualification or '', border=1, align='C')
#             pdf.ln()

#         # Add professional details in tabular form
#         pdf.ln(10)
#         pdf.cell(200, 10, txt="E. Professional Details", ln=True, align='L')
#         pdf.cell(60, 10, txt="Institution", border=1, align='C')
#         pdf.cell(30, 10, txt="Year", border=1, align='C')
#         pdf.cell(50, 10, txt="Certification", border=1, align='C')
#         pdf.cell(50, 10, txt="Location", border=1, align='C')
#         pdf.ln()
#         for professional in professionals:
#             pdf.cell(60, 10, txt=professional.institution, border=1, align='C')
#             pdf.cell(30, 10, txt=str(professional.year), border=1, align='C')
#             pdf.cell(50, 10, txt=professional.certification, border=1, align='C')
#             pdf.cell(50, 10, txt=professional.location or '', border=1, align='C')
#             pdf.ln()

#         # Add declarations signatures and dates
#         if declarations:
#             pdf.ln(10)
#             pdf.cell(200, 10, txt="F. Declarations", ln=True, align='L')
#             for declaration in declarations:
#                 pdf.ln(10)
#                 if declaration.reps_signature:
#                     reps_signature_path = os.path.join(tmpdirname, 'reps_signature.png')
#                     with open(reps_signature_path, 'wb') as img_file:
#                         img_file.write(declaration.reps_signature)
#                     pdf.image(reps_signature_path, x=10, y=pdf.get_y(), w=30, h=15)
#                 if declaration.employees_signature:
#                     employees_signature_path = os.path.join(tmpdirname, 'employees_signature.png')
#                     with open(employees_signature_path, 'wb') as img_file:
#                         img_file.write(declaration.employees_signature)
#                     pdf.image(employees_signature_path, x=160, y=pdf.get_y(), w=30, h=15)
#                 pdf.ln(20)
#                 pdf.cell(30, 10, txt="Representative Signature", ln=False, align='C')
#                 pdf.cell(130, 10, txt="Employee Signature", ln=False, align='C')
#                 pdf.ln(10)
#                 date_str = declaration.declaration_date.strftime("%d%m%Y")
#                 pdf.cell(30, 10, txt=date_str, ln=False, align='C')
#                 pdf.cell(130, 10, txt=date_str, ln=False, align='C')
#                 pdf.ln(10)

#         # Add page numbers at the bottom right corner
#         for i in range(1, pdf.page_no() + 1):
#             pdf.page = i
#             pdf.set_y(-15)
#             pdf.set_font("Arial", size=8)
#             pdf.cell(0, 10, f'Page {i}', 0, 0, 'R')

#         # Save the PDF to the specified file path
#         pdf.output(file_path)



# Define a permanent directory for temporary files
# TEMP_FILES_DIR = Path("temp_files")
# TEMP_FILES_DIR.mkdir(exist_ok=True)
# def generate_pdf_for_bio_data(db: Session, bio_data_id: uuid.UUID) -> str:
#     # Fetch the bio_data record
#     bio_data = db.query(BioData).filter_by(id=bio_data_id).first()
#     if not bio_data:
#         raise ValueError(f"BioData with id {bio_data_id} not found.")
    
#     first_name = bio_data.first_name
#     surname = bio_data.surname

#     # Create the file path in the permanent directory
#     file_path = TEMP_FILES_DIR / f"bio_data_{bio_data_id}.pdf"

#        # Initialize PDF canvas
#     buffer = BytesIO()
#     pdf = canvas.Canvas(buffer, pagesize=letter)
#     pdf.setTitle(f"PERSONAL RECORDS FORM - {first_name} {surname}")

#     # Function to resize images to 100x100
#     def resize_image(image_data):
#         try:
#             img = Image.open(BytesIO(image_data))
#             img.thumbnail((100, 100), Image.ANTIALIAS)
#             return img
#         except UnidentifiedImageError:
#             return None

#     # Helper function to add an image to PDF with caption
#     def add_image_to_pdf(image_data, caption, x, y):
#         img = resize_image(image_data)
#         if img:
#             img_buffer = BytesIO()
#             img.save(img_buffer, format="PNG")
#             img_buffer.seek(0)
#             pdf.drawImage(img_buffer, x, y, width=100, height=100)
#             pdf.drawString(x, y - 0.2 * inch, caption)
#         else:
#             pdf.drawString(x, y, f"Error: Could not identify image for {caption}")

#     # Helper function to add a page with header and footer
#     def add_page_with_header_footer(page_num):
#         pdf.showPage()
#         pdf.drawString(1 * inch, 10.5 * inch, f"PERSONAL RECORDS FORM - {first_name} {surname}")
#         pdf.drawString(7.5 * inch, 0.5 * inch, f"Page {page_num}")

#     page_num = 1
#     y_position = 10 * inch

#     # Add bio_data details to PDF
#     pdf.drawString(1 * inch, y_position, f"Bio Data ID: {bio_data.id}")
#     y_position -= 0.5 * inch
#     pdf.drawString(1 * inch, y_position, f"Name: {bio_data.first_name} {bio_data.surname}")
#     y_position -= 0.5 * inch

#     # Function to fetch column names dynamically
#     def get_column_names(obj):
#         return [col.key for col in obj.__table__.columns if col.key not in ['id', f'{obj.__tablename__}_id']]

#     # Iterate over related tables to fetch data
#     related_tables = [
#         (bio_data.employment_detail, "Employment Detail"),
#         (bio_data.bank_details, "Bank Details"),
#         (bio_data.academics, "Academics"),
#         (bio_data.professionals, "Professionals"),
#         (bio_data.qualifications, "Qualifications"),
#         (bio_data.employment_histories, "Employment Histories"),
#         (bio_data.family_infos, "Family Infos"),
#         (bio_data.emergency_contacts, "Emergency Contacts"),
#         (bio_data.next_of_kins, "Next of Kin"),
#         (bio_data.declarations, "Declarations")
#     ]

#     for related_obj, table_name in related_tables:
#         if related_obj:
#             if isinstance(related_obj, list):  # Check if related_obj is a list
#                 for item in related_obj:
#                     if y_position < 2 * inch:
#                         add_page_with_header_footer(page_num)
#                         page_num += 1
#                         y_position = 10 * inch

#                     pdf.drawString(1 * inch, y_position, f"Table: {table_name}")
#                     y_position -= 0.3 * inch

#                     # Get column names to exclude 'id' and 'table_id'
#                     column_names = get_column_names(item)
#                     for column in column_names:
#                         if y_position < 1 * inch:
#                             add_page_with_header_footer(page_num)
#                             page_num += 1
#                             y_position = 10 * inch

#                         pdf.drawString(1.2 * inch, y_position, f"{column}: {getattr(item, column)}")
#                         y_position -= 0.3 * inch
#             else:
#                 if y_position < 2 * inch:
#                     add_page_with_header_footer(page_num)
#                     page_num += 1
#                     y_position = 10 * inch

#                 pdf.drawString(1 * inch, y_position, f"Table: {table_name}")
#                 y_position -= 0.3 * inch

#                 # Get column names to exclude 'id' and 'table_id'
#                 column_names = get_column_names(related_obj)
#                 for column in column_names:
#                     if y_position < 1 * inch:
#                         add_page_with_header_footer(page_num)
#                         page_num += 1
#                         y_position = 10 * inch

#                     pdf.drawString(1.2 * inch, y_position, f"{column}: {getattr(related_obj, column)}")
#                     y_position -= 0.3 * inch

#     # Add images from 'declarations' table with column names
#     if bio_data.declarations:
#         if y_position < 2 * inch:
#             add_page_with_header_footer(page_num)
#             page_num += 1
#             y_position = 10 * inch

#         pdf.drawString(1 * inch, y_position, "Declaration:")
#         y_position -= 0.5 * inch

#         for declaration in bio_data.declarations:
#             if declaration.reps_signature:
#                 add_image_to_pdf(declaration.reps_signature, "Reps Signature", 1 * inch, y_position)
#                 y_position -= 2 * inch

#             if declaration.employees_signature:
#                 add_image_to_pdf(declaration.employees_signature, "Employees Signature", 4 * inch, y_position)
#                 y_position -= 2 * inch

#             if declaration.declaration_date:
#                 pdf.drawString(1 * inch, y_position, f"Declaration Date: {declaration.declaration_date.strftime('%Y-%m-%d')}")
#                 y_position -= 0.5 * inch     

#     pdf.save()
#     buffer.seek(0)
#     with open(file_path, "wb") as f:
#         print("get buffer: ", buffer.getbuffer())
#         f.write(buffer.getvalue())
#     print("file_path :-> ", file_path)
#     return str(file_path)



