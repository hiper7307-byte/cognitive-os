from pydantic import BaseModel
from typing import List, Dict

class UserInput(BaseModel):
    user_id: str
    text: str

class Intent(BaseModel):
    task_type: str
    confidence: float
    entities: Dict

class TaskStep(BaseModel):
    action: str
    params: Dict

class TaskPlan(BaseModel):
    steps: List[TaskStep]
    risk_level: str
