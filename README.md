# Retry

An AI agent that recovers revenue that's slipping away. Built for the Razorpay AI Buildathon, Track: AI Revenue Recovery.

## What this is

Businesses lose money quietly. A payment fails, an invoice goes overdue, and nobody notices until it's too late to do anything about it. Retry watches for these moments, figures out why they happened, decides what to do about it, and does it, all while staying inside strict rules about who it can contact, when, and how often.

It's not just a dashboard that shows you a problem. It actually diagnoses the failure, picks the right recovery action, checks that action against compliance rules, executes it in a sandbox environment, and writes down exactly what it did and why. You can open any case and read the full story of what happened to it, step by step.

![Dashboard hero](assets/dashboard_hero.png)
*The main dashboard: live outcome feed, key recovery metrics, and zero guardrail violations.*

## Results

Diagnosis accuracy, measured against a 20-case hand-labeled golden evaluation set, came out to 100% on severity classification and 100% on root cause identification. This run was handled entirely by the local Ollama model (llama3.1:8b), with zero cloud API calls needed. In earlier runs, before the local model was available, the same pipeline correctly cascaded through Claude, then Gemini, then Groq, each fallback logged with the specific reason it occurred, for example a low credit balance or a daily quota limit.

The batch-scale recovery numbers below come from a full run through Simulation Control, not the smaller eval set above.

- Cases processed: 93
- Amount recovered: ₹92,276.55
- No-intervention baseline: ₹28,350.21
- Incremental gain from the agent: ₹63,926.34
- Recovery rate: 39.8%
- Guardrail violations: 0 (one action currently held pending by an active guardrail, awaiting a compliant contact window, which is correct behavior, not a violation)

## How it works

The pipeline has six stages:

1. Detection. A Razorpay webhook fires when a payment fails, or a receivable goes overdue. Retry catches it.
2. Diagnosis. An AI model reads the failure code and description and figures out the root cause. Was it a temporary problem, like insufficient funds, or a permanent one, like an expired card? This matters a lot, because retrying a permanent failure is pointless and can hurt your standing with payment networks.
3. Decision. Based on the diagnosis, Retry decides what to do. Retry the payment. Send an email. Send an SMS. Escalate to a human. Or do nothing.
4. Guardrails. Before anything happens, a set of plain Python functions checks the decision against hard rules. Is it within the allowed contact hours? Has this customer already been contacted too many times today? Did they opt out? Is this a hard decline that should never be retried? These checks are code, not instructions to the AI. The AI cannot talk its way past them.
5. Execution. If the guardrails pass, the action actually runs, in a sandbox. No real money moves and no real messages go to real people, but the mechanics are the same as they would be in production.
6. Audit. Every single step above gets written to a permanent, append-only log. Nothing gets overwritten. You can look back at any case and see exactly what happened and why.

## Why it uses five different AI providers

While building this, we ran into real problems. Free trial credit ran out. Daily quotas got hit. Rate limits kicked in mid batch run. Instead of treating that as a dead end, we built a fallback chain, so the system tries one provider, and if that fails, tries the next one, and logs exactly why each attempt succeeded or failed.

The order is: a local model running on the machine through Ollama, then Claude, then Gemini, then Groq, then a deterministic rule engine as a last resort if every AI provider is unavailable.

Every diagnosis and decision records which one of these actually produced it. We've tested this two ways: a full run where the local model handled every single case with no cloud calls at all, and a full run where the cloud providers correctly took over from each other as earlier ones hit real credit and quota limits. Both worked.

![Provider breakdown](assets/d2.png)
*Multi-provider resilience in action. This run resolved entirely through the local Ollama model, with the rule engine handling B2B promise-to-pay transitions.*

## Tech stack

Backend: Python, FastAPI, SQLite for local development, PostgreSQL for production, SQLAlchemy, Pydantic.

AI: a hand written tool use loop across Ollama, Claude, Gemini, and Groq. No agent framework like LangGraph or CrewAI. We wrote the orchestration ourselves so every part of it is inspectable and debuggable.

Payments: the Razorpay Python SDK, running in test mode against real decline codes and real webhook signatures.

Frontend: Next.js, React, Tailwind CSS.

## Project layout

```
backend/
  app/
    main.py           entrypoint and webhook receiver
    config.py          settings and environment variable handling
    db.py               database engine and session setup
    models.py         database tables
    schemas.py       structured data shapes for AI outputs
    pipeline/
      detection.py      catches and simulates payment failure events
      diagnosis.py      runs the multi provider diagnosis step
      decision.py       runs the multi provider decision step
      guardrails.py    the compliance checks, written in plain Python
      metrics.py         calculates the batch level numbers
    api/                 the actual HTTP endpoints
  eval/
    eval_set.json          20 hand labeled test cases
    run_eval.py             script that checks diagnosis accuracy against them
  requirements.txt
frontend/
  src/
    app/                 the Next.js pages
    components/          shared UI pieces like the navbar
    lib/                     the API client
  package.json
```

## Setting it up

You'll need a `.env` file inside the `backend` folder.

```
DATABASE_URL=postgresql://user:password@localhost:5432/dbname

ANTHROPIC_API_KEY=your-key-here
GEMINI_API_KEY=your-key-here
GEMINI_MODEL=gemini-3.6-flash
GROQ_API_KEY=your-key-here
GROQ_MODEL=openai/gpt-oss-120b
OLLAMA_BASE_URL=http://localhost:11434/v1
OLLAMA_MODEL=llama3.1:8b


```

None of the AI provider keys are required. Leave them all blank and the system still works, it just falls back to the deterministic rule engine for every case.

### Running the backend

```
python --version
pip install -r backend/requirements.txt
```

On macOS or Linux:
```
export PYTHONPATH=.
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

On Windows, in PowerShell:
```
$env:PYTHONPATH="."
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

Check it's running at `http://127.0.0.1:8000/`.

### Running the accuracy evaluation

```
python backend/eval/run_eval.py
```

This runs the 20 golden test cases through the diagnosis pipeline and prints how accurate it was, both on severity classification and root cause identification.

### Running the frontend

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Trying it out yourself

![Case list](assets/d3.png)
*Every case tracked with its leak type, recovery status, and customer contact preference. Note the opted-out customer above, correctly excluded from contact.*

Seed some data first. Go to Simulation Control, type in a number like 15, and click Clear and Seed Events. This wipes whatever was there before and generates fresh cases with full pipeline traces.

![Simulation control](assets/d4.png)
*The Simulation Control Room includes built-in edge case test workflows for verifying guardrails and Promise-to-Pay reactivation, so testing is part of the product itself, not a separate script.*

To see the compliance guardrails actually block something, click the Night preset in the Time Travel Console. Then open a case and look at Stage 4. You'll see the calling window check fail, because it's outside the allowed hours. The recovery action will sit there as pending. Click the Morning preset, and go back to that case. The pending action will now show as executed.

To see the promise to pay reactivation, find a receivable case, click Log Promise to Pay, and set a date and amount. Then click the plus five days preset. The system will notice the promise date passed with no payment, mark it broken, and automatically send out a new recovery message.

Open any case's detail page and scroll through all six stages. Each diagnosis and decision stage shows a small badge telling you which provider handled it, Claude, Gemini, Groq, Ollama, or the rule engine, along with the reasoning it gave.

## What this doesn't do

We deliberately focused on two directions: payment degradation with root-cause diagnosis and recovery, and a B2B Promise-to-Pay tracker for overdue receivables. Checkout abandonment, subscription-specific flows, mandate retry sequencing, and Hinglish voice recovery were out of scope for this build. We chose to build these two workflows properly with a live audit trail and deterministic guardrails rather than covering multiple directions shallowly.

Everything runs against Razorpay's test mode. No real transactions happen anywhere in this project.

The local Ollama provider only works when you're running this on your own machine. If you deploy this somewhere else, it will correctly notice Ollama isn't reachable and fall through to the cloud providers instead.

Authentication is included for demonstration (with 1-click demo auto-fill and role selection), but there is no multi-tenant data isolation between multiple businesses. This is a working prototype of the recovery pipeline, not a commercial multi-tenant SaaS.

## License

MIT. See the LICENSE file.
