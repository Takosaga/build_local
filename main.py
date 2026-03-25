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
from llm.prompts import get_setup_prompt, get_ongoing_prompt
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
    return templates.TemplateResponse(request, "wizard.html", {
        "step": state.current_step,
        "business_data": state.business_data,
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
        increment_questions_asked()
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

    if mode == "setup" and should_advance_from_info_step() and get_state().current_step == 2:
        advance_step()

    async def token_stream():
        for char in response_text:
            yield f"data: {json.dumps({'delta': char})}\n\n"
            await asyncio.sleep(0)
        yield "data: [DONE]\n\n"

    return StreamingResponse(token_stream(), media_type="text/event-stream")


@app.post("/wizard/finalise")
async def wizard_finalise():
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
