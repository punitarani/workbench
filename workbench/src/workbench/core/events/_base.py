from pydantic import BaseModel, ConfigDict


class Payload(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
