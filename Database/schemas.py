from pydantic import BaseModel, ConfigDict, Field

class ReadingBase(BaseModel):
    sensor: str = Field(min_length=1, max_length=20)
    content: float
    
    
class ReadingCreate(ReadingBase):
    pass 


class ReadingResponse(ReadingBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    date_timestamp: str
    



