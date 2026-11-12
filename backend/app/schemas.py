"""Bentuk data masuk/keluar API akun. Aturannya sama dengan validasi di frontend."""
from pydantic import BaseModel, Field, field_validator

EMAIL_RE = r"^[^\s@]+@[^\s@]+\.[^\s@]+$"
USERNAME_RE = r"^[A-Za-z0-9_.]{3,20}$"
TELEPON_RE = r"^\+?[0-9\s-]{8,16}$"


def _bersih_email(v):
    return v.strip().lower() if isinstance(v, str) else v


class RegisterIn(BaseModel):
    email: str = Field(pattern=EMAIL_RE, max_length=255)
    password: str = Field(min_length=8, max_length=128)
    _email = field_validator("email", mode="before")(_bersih_email)


class LoginIn(BaseModel):
    email: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=128)
    _email = field_validator("email", mode="before")(_bersih_email)


class ProfilIn(BaseModel):
    nama: str = Field(min_length=1, max_length=100)
    username: str = Field(pattern=USERNAME_RE)
    email: str = Field(pattern=EMAIL_RE, max_length=255)
    telepon: str = Field(pattern=TELEPON_RE)
    _email = field_validator("email", mode="before")(_bersih_email)

    @field_validator("nama", "username", "telepon", mode="before")
    @classmethod
    def _strip(cls, v):
        return v.strip() if isinstance(v, str) else v


class SandiIn(BaseModel):
    lama: str = Field(min_length=1, max_length=128)
    baru: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    nama: str
    username: str
    email: str
    telepon: str
    role: str       # 'Admin' / 'Staf' (sesuai tampilan frontend)
