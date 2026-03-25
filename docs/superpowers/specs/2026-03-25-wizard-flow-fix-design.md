# Wizard Flow Fix — Design Spec
**Date:** 2026-03-25
**Branch:** testing_1

## Problem

The setup wizard shows a blank white screen after the user submits the Step 0 form. Nothing prompts the user to act. Two root causes:

1. No mechanism triggers the AI to speak first when the chat page loads.
2. Step numbering in the code is misaligned with the v3 design, so step-advance logic never fires (the `current_step == 2` guard is never reached because the step stays at 1).

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

- Runs the LLM with a step-specific opening prompt.
- Streams the response as SSE (same format as `/chat`).
- Saves the AI message to conversation history.
- Returns 204 if called outside steps 1–3 (no-op).

**`app.js` change:**

On page load, if a chat container is present, immediately call `GET /wizard/greet`. Stream the response into the messages area exactly like a normal chat reply. Disable the text input and Send button until streaming is complete. Re-enable them once `[DONE]` is received.

## Section 2: Step-Specific Opening Prompts

Three greet prompts added to `prompts.py`:

- **Step 1 greet:** "You are helping a small business owner set up ERPNext. Their business is {business_name}, a {business_type} in {location}. Ask them ONE friendly question: do they have existing customer/product data they'd like to import, or would they prefer to start with a demo setup? Nothing else."
- **Step 2 greet:** "You are helping {business_name} set up ERPNext. Ask your first question to understand their business operations. One question only. Start with inventory: do they manage stock or work to order?"
- **Step 3 greet:** "Summarise what has been configured for {business_name} based on the conversation so far. Present it clearly in plain language. Then invite them to change anything before finalising. End with: 'When you're happy, click Finalise Setup below.'"

All three greet prompts are kept short and directive so the LLM does not ramble.

## Section 3: Step Advance Logic

Each step has one explicit rule:

| Step | Advance rule | Implementation |
|------|-------------|----------------|
| 1 → 2 | After 1 user reply | `/chat` checks `current_step == 1`, advances before returning response |
| 2 → 3 | After `questions_asked >= 5` | Fix existing guard: `current_step == 2` (was unreachable, now reachable) |
| 3 → complete | User clicks Finalise button | `POST /wizard/finalise` → `mark_complete()` → redirect to `/` |

The `increment_questions_asked()` call in `/chat` only fires when `current_step == 2`.

## Section 4: UI Changes

### `wizard.html`
- Change `{% if step >= 4 %}` → `{% if step == 3 %}` for the Finalise Setup button.
- Add a step indicator above the chat: e.g. `Step 1 of 3` / `Step 2 of 3` / `Step 3 of 3` (steps 1–3 map to "1 of 3", "2 of 3", "3 of 3").
- Input field starts disabled; JS enables it after greet completes.

### `app.js`
- On DOM load: if `#messages` exists, call `GET /wizard/greet`, stream response, re-enable input on `[DONE]`.
- No other changes to chat submit logic.

### `chat.html`
- No changes. Ongoing chat is unaffected.

## Files Changed

| File | Change |
|------|--------|
| `main.py` | Add `GET /wizard/greet` endpoint; fix step-advance guards in `/chat` |
| `llm/prompts.py` | Add `get_greet_prompt(step, ...)` function with 3 step prompts |
| `wizard/flow.py` | Restrict `increment_questions_asked` to step 2 only |
| `ui/templates/wizard.html` | Fix Finalise button condition; add step indicator; disable input on load |
| `ui/static/app.js` | Call `/wizard/greet` on page load; disable/re-enable input |

## Out of Scope

- CSV import (already returns 501)
- Visual design / styling changes beyond the step indicator
- ERPNext tool execution changes
