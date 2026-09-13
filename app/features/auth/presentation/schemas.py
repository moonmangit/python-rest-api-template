from pydantic import BaseModel, ConfigDict


class ApplicationGrantUpdate(BaseModel):
    enabled: bool


class ApplicationGrantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    application: str
    enabled: bool


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_user_id: int | None
    target_user_id: int | None
    action: str
    entity_type: str
    entity_id: str | None
    metadata_json: dict | None
    created_at: object
