from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: EmailStr
    role: str
    is_active: bool
    created_at: datetime


class RegisterRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    pseudo: str = Field(min_length=2, max_length=40, pattern=r"^[\w .-]+$")
    grade_id: int | None = Field(default=None, gt=0)
    class_id: int | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def class_requires_grade(self):
        if self.class_id is not None and self.grade_id is None:
            raise ValueError("grade_id est requis lorsque class_id est fourni")
        return self


class LoginRequest(StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenRead(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class CycleCreate(StrictModel):
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=100)


class CycleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str


class GradeCreate(StrictModel):
    cycle_id: int | None = Field(default=None, gt=0)
    code: str = Field(min_length=2, max_length=30, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    sort_order: int = Field(default=0, ge=0)


class GradeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    cycle_id: int | None
    code: str
    name: str
    sort_order: int


class ClassCreate(StrictModel):
    grade_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=80)
    academic_year: str = Field(pattern=r"^\d{4}-\d{4}$")


class ClassRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_id: int
    name: str
    academic_year: str


class SubjectCreate(StrictModel):
    code: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)


class SubjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str
    is_active: bool


class ChapterCreate(StrictModel):
    grade_id: int = Field(gt=0)
    subject_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=160)
    sort_order: int = Field(default=0, ge=0)


class ChapterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    grade_id: int
    subject_id: int
    title: str
    sort_order: int
