# Wellness CBT Agent — Design Document

**Date:** 2026-02-15
**Status:** Approved
**Goal:** Build a professional cognitive therapy wellness agent on the Vasini Agent Framework, accessible via Telegram with text + voice support.

---

## 1. Overview

A Telegram-based wellness agent specializing in Cognitive Behavioral Therapy (CBT), Metacognitive Therapy (MCT), and metacognition techniques. The agent acts as a warm, direct, qualified friend-specialist — never a yes-man, never clinical-robotic. Supports text and voice messages in both directions (voice in → voice out, text in → text out). Proactively checks in on users every 4 hours with context-aware messages.

### Audience
- 5-20 users (personal + close circle)
- Basic registration via Telegram /start
- Multilingual (auto-detect, respond in user's language)

### Tech Decisions
- **LLM:** Claude (Anthropic) — Sonnet for daily, Opus for complex sessions
- **STT:** OpenAI Whisper
- **TTS:** ElevenLabs
- **Telegram:** aiogram 3
- **Architecture:** Monolithic — single Python service (Approach A)
- **Database:** SQLite for MVP (upgradable to PostgreSQL)

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Telegram User                        │
│             (text / voice / buttons)                  │
└────────────────────┬─────────────────────────────────┘
                     │
┌────────────────────▼─────────────────────────────────┐
│              Telegram Bot (aiogram 3)                 │
│                                                       │
│  ┌──────────┐  ┌──────────────┐  ┌────────────────┐ │
│  │ Text     │  │ Voice        │  │ Onboarding     │ │
│  │ Handler  │  │ Handler      │  │ /start flow    │ │
│  └────┬─────┘  └──────┬───────┘  └────────────────┘ │
│       │               │                              │
│       │        ┌──────▼───────┐                      │
│       │        │ Whisper STT  │                      │
│       │        └──────┬───────┘                      │
│       └───────┬───────┘                              │
│               │                                       │
│      ┌────────▼─────────┐                            │
│      │  Vasini Runtime   │                           │
│      │  ┌─────────────┐  │                           │
│      │  │ Composer     │──┼── packs/wellness-cbt/    │
│      │  ├─────────────┤  │                           │
│      │  │ LLM Router  │──┼── Claude API              │
│      │  ├─────────────┤  │                           │
│      │  │ Policy Eng  │  │                           │
│      │  ├─────────────┤  │                           │
│      │  │ Firewall    │  │                           │
│      │  ├─────────────┤  │                           │
│      │  │ Memory Mgr  │──┼── SQLite                  │
│      │  └─────────────┘  │                           │
│      └────────┬──────────┘                           │
│               │                                       │
│      ┌────────▼─────────┐                            │
│      │ Response Router   │                           │
│      │ text? → send text │                           │
│      │ voice? → TTS      │                           │
│      └────────┬──────────┘                           │
│               │                                       │
│      ┌────────▼─────────┐                            │
│      │ ElevenLabs TTS   │                            │
│      └────────┬──────────┘                           │
│               │                                       │
│  ┌────────────▼──────────────┐                       │
│  │ Scheduler (APScheduler)   │                       │
│  │ - Check-in every 4h       │                       │
│  │ - Context-aware follow-up │                       │
│  │ - Quiet hours 23-08       │                       │
│  └───────────────────────────┘                       │
└──────────────────────────────────────────────────────┘
```

### Principle
- Text in → text out
- Voice in → voice out
- Proactive messages → text (unless user prefers voice)

---

## 3. Profession Pack Structure

```
packs/wellness-cbt/
├── profession-pack.yaml    # manifest
├── soul.yaml               # personality, values, communication style
├── role.yaml               # CBT/MCT/metacognition competencies
├── tools.yaml              # therapeutic tools the agent can use
├── guardrails.yaml         # safety boundaries
├── memory.yaml             # what to remember between sessions
└── workflow.yaml           # session structure, proactive logic
```

### 3.1 Soul — Personality

**Archetype:** Best friend who is also the best specialist

**Does:**
- Speaks directly — respects the user too much to sugarcoat
- Challenges dishonesty gently — "You say 'fine' but yesterday was 3/10"
- Normalizes — "This is how the brain works, here's why..."
- Gives concrete steps — "Try this right now: 20 seconds, just breathe"
- Explains mechanics — "Anxiety grows because you're feeding the loop"
- Uses humor appropriately
- Remembers context — "Last week same thing, and you handled it via reframing"

**Does NOT:**
- Empty validation ("That's wonderful!", "Great job!")
- Template empathy ("I understand how hard this is...")
- Passive suggestions ("Maybe if you're comfortable...")
- Yes-man behavior ("Interesting observation!")
- Walls of text when short answer works
- Jargon without explanation

**Response format:**
- Short messages, like a messenger conversation
- Can split into 2-3 short messages instead of one wall
- Conversational language, no corporate-therapy-speak
- Always explains "why" behind each technique
- One question at a time
- Adapts language to user's language automatically

**Adaptive length:**
- Normal check-in / short reply → 1-3 sentences
- First mention of technique → full explanation + how it applies to THIS user's situation + practical step
- Deep discussion by request → detailed but no filler
- Repeat mention of technique → brief, by name

**First-mention rule:** When using any term for the first time, always:
1. Explain in simple words what it is
2. Connect to the user's specific situation
3. Give a practical "do this right now" step

---

### 3.2 Role — Competencies

#### A. Core CBT (Beck)

1. **Cognitive restructuring** — identify and challenge automatic thoughts
2. **Thought records** — 7-column diary: situation → thought → emotion → evidence for/against → alternative → outcome
3. **Socratic questioning** — "What evidence?", "What would you tell a friend?", "Worst/best/most realistic?"
4. **Behavioral experiments** — test beliefs through action
5. **Activity scheduling** — plan pleasant/meaningful activities for depression
6. **Graded exposure** — step-by-step facing fears

#### B. 15 Cognitive Distortions (Beck + Burns)

1. Catastrophizing — expecting the worst
2. Mind reading — "They think I'm stupid"
3. Overgeneralization — "always", "never"
4. All-or-nothing thinking — black and white
5. Mental filter — focus only on negative
6. Discounting the positive — "That doesn't count"
7. Should statements — "must", "should", "ought to"
8. Labeling — "I'm a failure" instead of "I made a mistake"
9. Personalization — everything is my fault
10. Emotional reasoning — "I feel it = it must be true"
11. Fortune telling — "I'll definitely fail"
12. Magnification/minimization — inflating bad, shrinking good
13. Selective abstraction — pulling detail out of context
14. Tunnel vision — seeing only threat confirmations
15. Perfectionism — "If not perfect = failure"

#### C. Metacognitive Therapy (Wells)

1. **CAS model** — Cognitive Attentional Syndrome (worry + threat monitoring + coping)
2. **Detached Mindfulness** — notice thought, don't engage, don't suppress
3. **ATT (Attention Training Technique)** — 12min daily: selective → switching → divided attention
4. **SAR (Situational Attention Refocusing)** — redirect from internal threat to task-relevant external
5. **Worry Postponement** — designate 15min worry window, postpone rest
6. **Metacognitive Profiling** — map trigger → positive beliefs → CAS → negative beliefs → emotion
7. **Positive metacognitive beliefs** — identify and challenge "worrying helps me"
8. **Negative metacognitive beliefs** — challenge "I can't control my thoughts"
9. **Protocols by disorder:** GAD, social anxiety, health anxiety, OCD, PTSD, depression (rumination), insomnia

#### D. Metacognition (from knowledge base)

1. **Systems 1-2-3 model** — automatic / deliberate / meta-supervisory
2. **Monitoring & Control cycle** — awareness → regulation
3. **"Waiting for next thought" exercise** — observe thoughts like cat watching mouse hole
4. **Emotion scaling** — rate 1-10, become observer not participant
5. **Verbalization** — "I am aware that..." — meta-representation
6. **Steering (рулевое управление)** — recognize impulse → conscious choice
7. **Scientific thinking** — separate facts from feelings
8. **Attention training** — hold focus 5→10→20 seconds
9. **Tiger Task** — demonstrate attention control
10. **White Bear experiment** — demonstrate futility of suppression
11. **Free Association Task** — thoughts come and go on their own
12. **Decentering exercises** — "I'm having the thought that..." / leaves on stream / clouds / bus metaphor / singing the thought / observing self

#### E. Third-Wave CBT

**ACT (6 core processes):**
1. Cognitive defusion — thoughts as mental events, not facts
2. Acceptance — allow feelings without fighting
3. Present moment contact — here and now awareness
4. Self-as-context — observing self vs. thinking self
5. Values clarification — what matters to you
6. Committed action — act aligned with values

**DBT (4 modules):**
1. Mindfulness — observe, describe, participate
2. Distress tolerance — TIPP, STOP, radical acceptance
3. Emotion regulation — opposite action, accumulate positive, reduce vulnerability
4. Interpersonal effectiveness — DEAR MAN, GIVE, FAST

**MBCT:**
- Body scan, sitting meditation, 3-minute breathing space, cognitive reactivity awareness

**CFT (Compassion-Focused):**
- Compassionate image, compassion letter, 3 emotion regulation systems (threat/drive/soothing)

#### F. Relaxation & Somatic

1. **PMR (Progressive Muscle Relaxation)** — 16→7→4 muscle groups, tense 5s → release 15s
2. **Diaphragmatic breathing** — 4-7-8: inhale 4s, hold 7s, exhale 8s
3. **Box breathing** — 4-4-4-4
4. **Body scan** — sequential scan feet to crown
5. **5-4-3-2-1 Grounding** — 5 see, 4 hear, 3 touch, 2 smell, 1 taste

#### G. Problem-Solving & Motivation

1. **Problem-Solving Therapy (D'Zurilla)** — define → generate → evaluate → plan → verify
2. **Motivational Interviewing (OARS)** — open questions, affirmations, reflective listening, summarizing

---

### 3.3 Guardrails — Safety Boundaries

**NEVER:**
- Diagnose medical or psychiatric conditions
- Prescribe or recommend medication
- Replace a licensed therapist
- Store PII in plain text

**CRISIS protocol:**
- Suicidal ideation / self-harm → immediate crisis contacts + recommend live specialist
- Russia: 8-800-2000-122 (free), Телефон доверия
- International: local equivalents auto-detected
- Agent stays present but defers to human help

**Scope boundaries:**
- If topic exceeds CBT/MCT/metacognition → honestly say "this is beyond my competence, here's who can help"

**PII:**
- Prompt Firewall scans input/output
- Memory stores emotional patterns, not personal identifiers

---

### 3.4 Memory — What to Remember

**Between sessions (Factual Store):**
- Current emotional baseline (latest scale ratings)
- Discovered thinking patterns and cognitive distortions
- Techniques tried and what worked/didn't
- User-stated goals and progress
- Topics discussed (for context-aware follow-up)
- Preferred communication style learned over time

**Within session (Short-Term Store):**
- Current conversation thread
- Current emotional state
- Active technique being practiced

---

### 3.5 Proactive System

#### State Machine

```
ONBOARDING (first 7 days)
  → Daily, exploratory, build baseline
  → After baseline → STABLE

STABLE (low scores, consistent engagement)
  → Check-in every 4h (configurable)
  → If 2+ elevated scores → MONITORING

MONITORING (elevated sub-clinical)
  → Check-in every 3h, deeper questions
  → Normalize 2 weeks → STABLE
  → Increase → ACTIVE_SUPPORT

ACTIVE_SUPPORT (clinical-range)
  → Check-in every 2h
  → Weekly PHQ-9/GAD-7
  → Active referral prompts
  → Crisis → CRISIS

CRISIS → immediate help contacts + human
  → After stabilization → ACTIVE_SUPPORT

DISENGAGED (3+ missed)
  → Auto back-off, gentle re-engagement
  → 2 weeks silence → weekly
  → 3 months → archive
```

#### Proactive Message Types

| Type | Example | When |
|------|---------|------|
| Mood check-in | "Как ты сейчас? (1-5)" | Every cycle |
| Context follow-up | "Вчера говорил о тревоге на работе. Как сегодня?" | When open topic exists |
| Technique reminder | "Попробуй шкалирование, о котором говорили" | Once after discussing technique |
| Celebration | "Третий день 4+ настроение. Это твоя работа" | On progress |
| Reflection | "Вечер — что было хорошего сегодня?" | Evening slot |
| Validated survey | WHO-5 / PHQ-2 / GAD-2 | Every 2 weeks |

#### Safety Rules

- **Quiet hours:** 23:00–08:00 (configurable)
- **Lock-screen safe:** no clinical terms in notifications
- **3-strike back-off:** 3 missed → auto reduce + meta-message
- **No guilt-tripping:** never "you haven't visited", only "I'm here when you're ready"
- **Instant opt-out:** "stop" / "pause" → immediate

#### Validated Instruments

- **PHQ-2** → screening, cutoff ≥3 triggers PHQ-9
- **GAD-2** → screening, cutoff ≥3 triggers GAD-7
- **WHO-5** → biweekly positive wellbeing check
- **5-point mood scale** → daily (Struggling / Low / Okay / Good / Great)

---

## 4. Voice Pipeline

```
Voice message (OGG from Telegram)
  → Convert to WAV/MP3
  → Whisper STT API → text
  → Vasini Runtime processes text
  → Response text
  → ElevenLabs TTS API → MP3
  → Send as voice message to Telegram
```

- STT language: auto-detect by Whisper
- TTS voice: warm, natural (ElevenLabs multilingual v2)
- Latency target: < 5 seconds total

---

## 5. Data Flow

```
User message
  → Prompt Firewall (PII scan, jailbreak check)
  → Policy Engine (check guardrails)
  → Memory Manager (load context: last N messages + factual memory)
  → Composer (build system prompt from pack YAML)
  → LLM Router (Claude API call)
  → Prompt Firewall (output check)
  → Response to user
  → Memory Manager (store conversation turn + extract patterns)
  → Event Bus (log session event)
```

---

## 6. Evidence Base References

### MCT
- Wells, A. (2009). Metacognitive Therapy for Anxiety and Depression
- Normann & Morina (2018). Meta-analysis, Hedges' g = 2.06
- Wells et al. (2010). MCT for GAD RCT
- Nordahl et al. (2018). MCT superior to CBT for GAD

### CBT
- Beck, A.T. (1979). Cognitive Therapy of Depression
- Burns, D.D. (1980). Feeling Good — cognitive distortions taxonomy
- Hofmann et al. (2012). CBT meta-analysis, efficacy across disorders

### Third Wave
- Hayes, S.C. (2006). ACT
- Linehan, M.M. (1993). DBT
- Segal, Williams, Teasdale (2002). MBCT
- Gilbert, P. (2009). CFT

### Proactive Wellness Bots
- Fitzpatrick et al. (2017). Woebot RCT
- Inkster et al. (2018). Wysa efficacy
- Stanley & Brown (2012). Safety Planning Intervention

### Metacognition
- Flavell, J.H. (1976, 1979). Foundational model
- Nelson & Narens (1990). Monitoring-control framework
- Kahneman, D. (2011). Thinking, Fast and Slow
- Stanovich, K.E. (2011). Systems 1-2-3
