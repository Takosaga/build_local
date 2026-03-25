import asyncio
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Form, UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

import config
from db.session import init_db, save_message, load_conversation
from erpnext.adapter import ERPNextAdapter
from llm.client import run_tool_loop, is_lm_studio_reachable
from llm.tools import get_setup_tools, get_ongoing_tools
from llm.prompts import get_setup_prompt, get_ongoing_prompt, get_greet_prompt
from wizard.state import get_state, update_business_data, mark_complete, reset, advance_step
from wizard.flow import get_mode, increment_questions_asked, should_advance_from_info_step


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
templates = Jinja2Templates(directory="ui/templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    state = get_state()
    if state.is_complete:
        return templates.TemplateResponse(request, "chat.html", {
            "business_name": state.business_data.get("name", "Your Business"),
        })
    step_names = {1: "Data Decision", 2: "Gathering Information", 3: "Review"}
    return templates.TemplateResponse(request, "wizard.html", {
        "step": state.current_step,
        "business_data": state.business_data,
        "step_name": step_names.get(state.current_step, ""),
    })


@app.post("/wizard/start")
async def wizard_start(
    business_name: str = Form(...),
    business_type: str = Form(...),
    location: str = Form(...),
    employees: str = Form(...),
):
    update_business_data({
        "name": business_name,
        "type": business_type,
        "location": location,
        "employees": employees,
    })
    advance_step()
    return {"status": "ok", "step": 1}


@app.get("/wizard/greet")
async def wizard_greet():
    state = get_state()
    current_step = state.current_step

    # Out-of-range: return empty stream
    if current_step not in (1, 2, 3):
        async def empty_stream():
            yield "data: [DONE]\n\n"
        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    # Idempotency: if already greeted for this step, replay last assistant message
    greeted_step = state.business_data.get("_greeted_step")
    if greeted_step == current_step:
        history = load_conversation(limit=40)
        cached = next(
            (m["content"] for m in reversed(history) if m["role"] == "assistant"),
            ""
        )
        async def cached_stream():
            for char in cached:
                yield f"data: {json.dumps({'delta': char})}\n\n"
                await asyncio.sleep(0)
            yield "data: [DONE]\n\n"
        return StreamingResponse(cached_stream(), media_type="text/event-stream")

    # Fresh greet: call LLM
    greet_prompt = get_greet_prompt(
        step=current_step,
        business_name=state.business_data.get("name", "your business"),
        business_type=state.business_data.get("type", "business"),
        location=state.business_data.get("location", ""),
    )
    # Pass full history for step 3 (summary needs context); empty list for steps 1 and 2
    history = load_conversation(limit=40) if current_step == 3 else []
    adapter = ERPNextAdapter()

    response_text = await asyncio.to_thread(
        run_tool_loop,
        messages=history,
        tools=[],
        adapter=adapter,
        system_prompt=greet_prompt,
    )

    save_message("assistant", response_text)
    update_business_data({"_greeted_step": current_step})

    async def greet_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(greet_stream(), media_type="text/event-stream")


@app.post("/wizard/upload")
async def wizard_upload(file: UploadFile = File(...), doctype: str = Form(...)):
    """CSV upload — import_csv tool not yet implemented."""
    raise HTTPException(status_code=501, detail="CSV import not yet available. Please use the demo setup option.")


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    user_message = body.get("message", "").strip()
    if not user_message:
        raise HTTPException(status_code=400, detail="Empty message")

    save_message("user", user_message)
    history = load_conversation(limit=40)

    state = get_state()
    mode = get_mode()
    adapter = ERPNextAdapter()

    if mode == "setup":
        system_prompt = get_setup_prompt(
            business_name=state.business_data.get("name", "your business"),
            business_type=state.business_data.get("type", "business"),
            location=state.business_data.get("location", ""),
            questions_asked=state.business_data.get("_questions_asked", 0),
            current_step=state.current_step,
        )
        tools = get_setup_tools()
    else:
        system_prompt = get_ongoing_prompt(
            business_name=state.business_data.get("name", "your business"),
            business_type=state.business_data.get("type", "business"),
        )
        tools = get_ongoing_tools()

    response_text = await asyncio.to_thread(
        run_tool_loop,
        messages=history,
        tools=tools,
        adapter=adapter,
        system_prompt=system_prompt,
    )

    save_message("assistant", response_text)

    # Step-advance checks — always run AFTER saving the assistant response.
    step_changed = False
    current_step = get_state().current_step

    if mode == "setup":
        if current_step == 1:
            # Step 1 → 2: advance after first user reply; reset counter and greeted flag.
            advance_step()
            update_business_data({"_questions_asked": 0, "_greeted_step": None})
            step_changed = True
        elif current_step == 2:
            # Step 2 → 3: advance after 5 questions.
            increment_questions_asked()
            if should_advance_from_info_step():
                advance_step()
                step_changed = True

    async def token_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        if step_changed:
            yield f"data: {json.dumps({'step_changed': True})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


@app.post("/wizard/finalise")
async def wizard_finalise():
    state = get_state()
    if state.current_step < 3:
        raise HTTPException(status_code=400, detail="Setup not yet at review step.")
    mark_complete()
    return {"status": "ok"}


@app.post("/wizard/reset")
async def wizard_reset():
    reset()
    return {"status": "ok"}


@app.get("/health")
async def health():
    adapter = ERPNextAdapter()
    return {
        "lm_studio": is_lm_studio_reachable(),
        "erpnext": adapter.is_reachable(),
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=config.FASTAPI_PORT, reload=False)
