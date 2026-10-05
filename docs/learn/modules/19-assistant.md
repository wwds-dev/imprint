# Chat

> **Outcome:** get one bounded answer, check it against your own acceptance
> criteria, and keep or discard the conversation deliberately.

## Prerequisites

- A question with a concrete deliverable and a way to verify it.
- A local model or an enabled cloud provider with a configured key and enough
  remaining budget.
- A fresh project when earlier conversation context would distract the model.

## Control atlas

| Control | What it changes |
|---|---|
| Tool | Adds the task frame, such as general chat, writing, summary, or rewrite. |
| Command | Inserts an optional reusable prompt scaffold. Check that it fits this request. |
| Provider and Model | Choose the route; Best Fit is guidance, not proof of quality. |
| Mode and API permissions | Limit local/cloud access and which keys may be used. |
| Prompt | The exact request. Include audience, format, constraints, and acceptance test. |
| Send / Stop | Start the guarded request or stop local work; a provider may already have billed. |
| Saved Chats | Reopen a previous thread or create a clean one. |

## Worked run

1. Open **Assistant** and create a new project if the task is unrelated to the
   current conversation.
2. Choose the Tool, Provider, and Model. Inspect the key status, Best Fit reason,
   cost estimate, and session/daily limits before a paid call.
3. Ask for one deliverable and a short list of assumptions. For example:
   “Summarise these notes into five decisions, quote no text not in the notes,
   and mark any unresolved decision.”
4. Press **Send** once. Read the status and Run Log if a result stalls. Do not
   repeat a paid request just because the local status has not refreshed.
5. Check the answer against your input, save the useful output outside the chat
   when it becomes an authoritative asset, and reopen it from Saved Chats.

## How to read the output

The answer is a generated draft. A confident sentence is not an observed fact,
and a suggested price is not a sale. Verify facts and current rules at their
source; use the specialist workspace for production work. Long conversations
send more context to cloud models and can consume more budget.

## Acceptance checklist

- [ ] The answer meets the requested format and includes the required items.
- [ ] Important claims were checked independently.
- [ ] The project can be reopened; any final asset has its own saved copy.
- [ ] The recorded cost is understood as an estimate or measured usage, as labelled.

## Verification

Reopen the saved conversation, compare the response to the prompt and source
material, and inspect the Run Log for its provider, status, and recorded cost.

## Cost, cancellation, and gates

Cloud requests send the conversation context to the selected provider. Local
Ollama requests stay on the machine. Permissions and budget checks run before
the request, but stopping after submission cannot guarantee a provider charge
will be reversed. Keep sensitive source material out of cloud context unless
that disclosure is authorised.

## Common failures

**No model appears:** check the provider key or local Ollama service, then
refresh the model list.
**A request is blocked:** read the exact reason; inspect permissions and budget
before retrying.
**The answer ignores earlier constraints:** start a clean project or restate the
constraint in the current prompt.

## Done when

The answer passes the acceptance checklist, important claims are verified, and
the useful result has a durable saved copy.

## Next action

For production, move the verified brief to the relevant specialist workspace.
For cost and routing decisions, revisit [Costs and limits](14-costs-limits.md)
and [Best Fit](12-best-fit.md).

## Recipe: ask one working question well

You will ask one bounded question — turning a scrappy week of notes into a
checked list of decisions — and end with a named, saved chat filed in a
project called *Field Notes*. Copy the example inputs exactly the first time,
then swap in your own notes. Each **Show me** closes this lesson, opens the
control it names and rings it; **Back to lesson** in the callout brings you
back to that step.

**Time:** about 15 minutes. **Cost:** one text request — you see its estimate
and approve it before anything is sent (free with a local Ollama model). A
resend is a second request and shows a second estimate.

### Step 1 — Start a clean project

Click **New Project** and name it. Imprint switches the Projects dropdown to
it and opens a fresh chat, so this question starts without leftover context
and everything you ask now files under it.

```
Project name:  Field Notes
```

[Show me](show:new_project_btn)

### Step 2 — Write one bounded question

A working question names its deliverable, its limits, and its format — that
is also how you will check the answer. Type this into the message box; the
notes travel inside the prompt, so the whole thing is copyable.

```
From the notes below, list the decisions that were actually made, one
line each, in the order they were decided. Quote nothing that is not in
the notes. If something is still open, list it separately under
"Unresolved". Format: two headed lists, no introduction.

Notes: Mon — agreed to move the launch from May to June. Tue — Sam owns
the pricing page now. Wed — we will not translate the docs this quarter.
Thu — maybe drop the webinar? nobody decided. Fri — new tagline approved
("Write once, publish everywhere"); budget for stock photos rejected.
```

[Show me](show:input_box)

### Step 3 — Let the router read it

Click **Auto Route**. The router reads your text and moves you to the
workspace it fits; a general question like this one stays in Chat. The **Chat
routing** card in the right rail fills in with the chosen agent, provider and
model — hover it for the why and the how-sure. The tooltip names one of three
honest tiers: *addressed* (you named a tool), *intent* (a keyword matched,
and it says which), or *fallback* (nothing matched, so Chat). A fallback is a
default, not a verdict.

[Show me](show:auto_route_btn)

### Step 4 — Choose who answers

Pick a provider and model. **BEST FIT** marks the recommended entry in both
dropdowns, and its hover text says why; any capable model handles this task.
Choose Ollama if you want the request to stay on your Mac and cost nothing —
a cloud provider also needs its checkbox ticked in the row below and a Mode
that allows cloud.

[Show me](show:provider_box)

### Step 5 — Check the price before sending

Click **Estimate Cost**: provider, model, approximate tokens, and the
estimated cost in euros — or "local execution" for Ollama. The same number
sits live in the right rail as **Next request**, and it moves as you edit the
prompt. It is an estimate of the request you are about to make, not a
measurement of anything.

[Show me](show:estimate_btn)

### Step 6 — Send once and watch it stream

Press **Send** once. A cloud request shows its estimate again and waits for
your approval before anything leaves the machine; then the answer streams
into the output box word by word, with elapsed and rough remaining time
below. **Stop** halts local work, but a cloud request already submitted may
still be billed — and do not resend just because the status has not refreshed.

**Good result:** five decisions in the order they were decided, the webinar
alone under *Unresolved*, nothing quoted that is not in the notes. **Weak
result:** an introduction, merged items, or invented detail — tighten the
format line and send again, knowing that costs a second request.

[Show me](show:send_btn)

### Step 7 — Keep or discard, deliberately

The finished chat appears under **Saved chats** in the left rail, filed in
*Field Notes* and titled by its first prompt until you rename it.
Double-click it and name it something you will recognise, for example
`Decisions — weekly template`; right-click to rename or move it to another
project; **Remove Chat** deletes a dead end. If this setup earned its keep,
click **Save Current Setup** so the project reopens with the same agent,
provider and model.

[Show me](show:history_list)
