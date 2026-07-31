from pydantic import BaseModel, Field, field_validator

from app.core.url_security import validate_public_http_url


class SourceResponse(BaseModel):
    id: int
    name: str
    url: str
    type: str
    language: str
    country: str | None
    topics: list[str] | None
    enabled: bool
    blacklisted: bool

    model_config = {"from_attributes": True}


class SourceCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    url: str = Field(..., min_length=1, max_length=512)
    type: str = Field(..., pattern=r"^(telegram|website|rss)$")
    language: str = Field(default="en", min_length=2, max_length=10)
    country: str | None = Field(default=None, min_length=2, max_length=10)
    topics: list[str] | None = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        return validate_public_http_url(value)
