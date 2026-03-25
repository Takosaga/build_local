# Wizard Flow Fix — Design Spec
**Date:** 2026-03-25
**Branch:** testing_1

## Problem

The setup wizard shows a blank white screen after the user submits the Step 0 form. Nothing prompts the user to act. Two root causes:

1. No mechanism triggers the AI to speak first when the chat page loads.
2. Step numbering is misaligned with the v3 design, so step-advance logic never fires. Additionally, `increment_questions_asked()` fires unconditionally on every `/chat` call regardless of step, poisoning the counter before step 2 begins.

## Goal

The user is always prompted and never guessing. Every step transition is driven by a clear, explicit rule. The AI speaks first on every chat step.

## Step Mapping

| Step | Name | Entry trigger | Exit trigger |
|------|------|--------------|--------------|
| 0 | Business Basics form | App load (not complete) | Form submit |
| 1 | Data Decision | Form submit | 1 user reply |
| 2 | Info Gathering | After step 1 | 5 AI questions answered |
| 3 | Review | After step 2 | "Finalise Setup" button |
| complete | Ongoing chat | Finalise clicked | — |

## Section 1: Auto-Greet Mechanism

**New endpoint:** `GET /wizard/greet`

**Idempotency:** Use a `_greeted_step` field in `business_data`. On every call, check `business_data.get("_greeted_step")`. If it equals `current_step`, stream the last assistant message from history as the SSE response and **do not call the LLM and do not save again**. If it does not match, run the LLM, save the response as role `"assistant"`, then set `_greeted_step = current_step` via `update_business_data({"_greeted_step": current_step})`.

**History passed to LLM:**
- Step 1: empty list `[]` — fresh conversation, no prior context.
- Step 2: empty list `[]` — the greet opens a new phase; full history would confuse the opening question.
- Step 3: full conversation history — the summary prompt must see all prior exchanges.

**Out-of-range steps:** If step is outside 1–3, return SSE with only `data: [DONE]\n\n`. Never return 204, so JS input re-enable logic still fires.

**SSE format:** Same as `/chat`: `data: {"delta": "..."}\n\n` per character, ending with `data: [DONE]\n\n`.

**`app.js` on DOM load:**
```
if document.querySelector('#wizard-chat') exists:
    disable #user-input and Send button
    call GET /wizard/greet
    stream response into #messages (same appendMessage logic as /chat)
    on [DONE]: re-enable #user-input and Send button
              if step_changed_flag is set: location.reload()
```

**Step-change SSE event:** When `/chat` advances a step, it emits one additional line before `[DONE]`:
```
data: {"step_changed": true}
```
In `app.js`, the SSE loop sets `let stepChangedFlag = false`. When parsing a line: if `parsed.step_changed === true`, set `stepChangedFlag = true`. Do **not** reload inside the loop. After the loop exits (or in the `finally` block), if `stepChangedFlag` is true, call `location.reload()`. This same flag-check applies in the `/wizard/greet` stream handler too (for the cached-path case, step_changed is never emitted, so the flag stays false).

## Section 2: Step-Specific Opening Prompts

New function in `prompts.py`:

```python
def get_greet_prompt(step: int, business_name: str, business_type: str, location: str) -> str
```

Three prompts (all parameters accepted by function; unused ones are ignored per step):

- **Step 1:** "You are helping a small business owner set up ERPNext. Their business is {business_name}, a {business_type} in {location}. Ask them ONE friendly question: do they have existing customer or product data they would like to import, or would they prefer to start with a demo setup? Ask nothing else."
- **Step 2:** "You are helping {business_name} (a {business_type} in {location}) set up ERPNext. Ask your first question to understand how their business operates. One question only. Start with inventory: do they manage stock, or do they work to order?"
- **Step 3:** "Summarise what has been configured for {business_name} based on the conversation history so far. Present it clearly in plain language — modules, data choices, tax, and any other details discussed. Then invite the user to change anything before finalising. End with exactly: 'When you are happy with everything, click Finalise Setup below.'"

## Section 3: Step Advance Logic

**Ordering within `/chat`:** The sequence for every `/chat` call is:
1. Save user message.
2. Load history.
3. Call LLM (`run_tool_loop`).
4. Save assistant response.
5. Check and apply step-advance conditions.
6. Emit `step_changed` event (if advanced).
7. Stream response.
8. Emit `[DONE]`.

Step-advance checks always occur **after** the assistant response is saved (step 4). This ensures the correct reply is in history before the page reloads and the next greet fires.

| Step | Advance rule | Implementation |
|------|-------------|----------------|
| 1 → 2 | After 1 user reply | After step 4: if `current_step == 1`, call `advance_step()`, then `update_business_data({"_questions_asked": 0, "_greeted_step": None})`, emit `step_changed`. |
| 2 → 3 | After `questions_asked >= 5` | After step 4: if `current_step == 2`, call `increment_questions_asked()`. Then if `should_advance_from_info_step()`, call `advance_step()`, emit `step_changed`. |
| 3 → complete | Finalise button | `POST /wizard/finalise` checks `current_step >= 3`; returns 400 otherwise. Calls `mark_complete()`. JS redirects to `/`. |

`increment_questions_asked()` is **only** called when `current_step == 2`. Remove the unconditional call at line 90 of `main.py`.

## Section 4: UI Changes

### `wizard.html`

- Add `id="wizard-chat"` to the existing `<div class="chat-container">` (do not add a new wrapper — this avoids breaking CSS).
- Change `{% if step >= 4 %}` → `{% if step == 3 %}` for the Finalise Setup button.
- Step indicator: pass `step_name` from the route alongside `step`. The `/` GET route sets `step_name` using a dict: `{1: "Data Decision", 2: "Gathering Information", 3: "Review"}`. Template renders: `<p class="step-indicator">Step {{ step }} of 3 — {{ step_name }}</p>` inside the `{% else %}` block (chat steps only).
- Add `disabled` attribute to `#user-input` and Send button in HTML. JS removes the attribute after greet `[DONE]`.

### `app.js`

```
// On DOM load
const wizardChat = document.querySelector('#wizard-chat');
if (wizardChat) {
  userInput.disabled = true;
  sendButton.disabled = true;
  // call GET /wizard/greet, stream into #messages
  // same SSE parsing as /chat
  // on [DONE]: re-enable, check stepChangedFlag → reload
}

// In /chat SSE handler — add step_changed detection:
let stepChangedFlag = false;
// inside the parse loop:
if (parsed.step_changed) stepChangedFlag = true;
// after loop (finally block):
if (stepChangedFlag) { location.reload(); return; }
```

### `chat.html`

No changes. Does not contain `#wizard-chat`, so greet never fires.

## Files Changed

| File | Change |
|------|--------|
| `main.py` | Add `GET /wizard/greet`; fix step-advance ordering and guards in `/chat`; emit `step_changed`; guard `/wizard/finalise`; pass `step_name` to template |
| `llm/prompts.py` | Add `get_greet_prompt(step, business_name, business_type, location)` |
| `wizard/flow.py` | Remove unconditional `increment_questions_asked`; it moves to `main.py` inside step-2 guard |
| `wizard/state.py` | No changes — existing `update_business_data` handles `_questions_asked` reset and `_greeted_step` |
| `ui/templates/wizard.html` | Add `id` to chat container; fix Finalise condition; add step indicator; add `disabled` to inputs |
| `ui/static/app.js` | Scope greet to `#wizard-chat`; handle `step_changed` with flag-then-reload pattern |

## Out of Scope

- CSV import (already returns 501)
- Visual styling beyond the step indicator
- ERPNext tool execution changes
- Server-side session locking for concurrent requests
- Handling LLM errors during step-1 advance (step advances regardless; error message still saved to history)
