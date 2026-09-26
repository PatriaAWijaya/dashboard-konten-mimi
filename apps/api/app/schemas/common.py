"""Schema umum: pesan & paginasi sederhana."""

from pydantic import BaseModel, ConfigDict


class MessageResponse(BaseModel):
    message: str


class BaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
