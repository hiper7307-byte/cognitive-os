from fastapi import APIRouter
from app.models import UserInput
from app.intent import parse_intent
from app.planner import generate_plan
from app.executor import execute_step
from app.memory import save, get_history

router = APIRouter()

@router.post("/task")
def handle_task(input: UserInput):
    intent = parse_intent(input.text)

    if intent["confidence"] < 0.6:
        return {"status": "clarify"}

    plan = generate_plan(intent)
    results = []

    for step in plan.steps:
        results.append(execute_step(step))

    save(input.user_id, input.text)

    return {
        "status": "done",
        "results": results,
        "history": get_history(input.user_id)
    }
