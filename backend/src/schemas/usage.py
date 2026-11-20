from pydantic import BaseModel, Field
class UsageBatchInput(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    source: str = Field(default='manual.json', max_length=200)
    records: list[dict] = Field(min_length=1, max_length=20000)
