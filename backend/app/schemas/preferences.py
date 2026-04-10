from pydantic import BaseModel, Field

VALID_TOPICS = {
    "politics", "military", "technology", "health",
    "science", "business", "sports", "culture", "environment",
}


class TopicPreference(BaseModel):
    topic: str
    weight: float = Field(ge=0.0, le=1.0)


class PreferencesResponse(BaseModel):
    preferences: list[TopicPreference]


class PreferencesUpdate(BaseModel):
    preferences: list[TopicPreference]
