# Proactive Coaching Bot (FSM + Context Intelligence)

## 1. Цель

Система должна по контексту диалога и истории пользователя проактивно предлагать релевантные практики, вести пользователя в стиле коуча, но с жёстким safety-контуром и управляемым FSM.

**Роль бота**: поддержка и практики самопомощи — не терапия. Бот ведёт как коуч: наблюдает, направляет, предлагает, но не давит и не ставит диагнозы.

**Мультиязычность**: бот автоматически определяет язык из текста пользователя и отвечает на нём. Язык кешируется в сессии, переопределяется при явной смене.

**Гибкость тем**: свободный диалог + смена практик + разные режимы (поговорить, пожаловаться, попросить совет, практика). Тон адаптивный — в wellness мягкий, в общих вопросах прямой и конкретный.

## 2. Компоненты

| Компонент | Назначение | Вход | Выход |
|---|---|---|---|
| Safety Gate | Детерминированный кризис-скрининг | user_message, locale | risk_level, safety_action |
| Language Resolver | Определение/кеш языка сессии | message, session_language | language |
| Context Analyzer (LLM) | Понимание состояния и контекста | последние N сообщений + данные БД | context_state |
| Opportunity Scorer | Решение, уместна ли проактивность сейчас | context_state + история отказов/согласий | opportunity_score, cooldown_flags |
| Practice Selector | Подбор практики из БД | context_state + opportunity_score | ranked_practices |
| Coach Policy Engine | Выбор стратегии ответа | context_state + ranked_practices | coaching_decision |
| Response Generator (LLM) | Формирование ответа в нужном стиле | coaching_decision + language | assistant_response |
| Consent Gate | Явное согласие перед стартом практики | user_reply | consent_status |
| FSM Orchestrator | Управление 2 FSM | events + current_state | next_state + side_effects |
| Output Safety Check | Проверка финального текста | assistant_response | approved/rewrite/block |
| Audit & Metrics | Наблюдаемость и QA | все события пайплайна | logs, metrics |

## 3. End-to-end пайплайн

```
User Message
    ↓
 1. Safety Gate (deterministic, multilingual)
    ├─ CRISIS → кризис-протокол (hotline, эскалация)
    └─ SAFE →
    ↓
 2. Session / Language Resolver (cache)
    ↓
 3. Context Analyzer (LLM + dialogue + DB history)
    │  Вход: сообщение, последние N сообщений, mood history,
    │        technique history, user profile
    │  Выход (structured):
    │  ├─ risk_level
    │  ├─ emotional_state (anxiety/rumination/avoidance/...)
    │  ├─ readiness_for_practice
    │  ├─ coaching_hypotheses
    │  ├─ confidence
    │  └─ candidate_constraints
    ↓
 4. Proactive Opportunity Scorer
    │  opportunity_score + cooldown
    ↓
 5. Practice Selector (retrieval + ranking + contraindications)
    ↓
 6. Coach Policy Engine (listen/explore/suggest/guide/answer)
    ↓
 7. Response Generator (LLM, объясняет почему предлагает)
    ↓
 8. Output Safety Check
    ↓
 9. Consent Gate (если suggest)
    │  Практика стартует ТОЛЬКО после согласия
    ↓
10. FSM Orchestrator (если согласие → старт/продолжение Practice FSM)
    ↓
11. Audit & Metrics
```

## 4. API контракты (ядро)

### POST /v1/context/analyze

**Request:**
```json
{
  "user_id": "uuid",
  "session_id": "uuid",
  "language": "ru",
  "user_message": "text",
  "dialogue_window": [
    {"role": "user", "text": "..."},
    {"role": "assistant", "text": "..."}
  ],
  "mood_history": [{"date": "2026-02-20", "mood": 3}],
  "practice_history": [{"practice_id": "grounding_5_4_3_2_1", "effectiveness": 0.7}],
  "user_profile": {"readiness": 0.6, "patterns": ["rumination"]}
}
```

**Response:**
```json
{
  "risk_level": "low|medium|high|crisis",
  "emotional_state": {"anxiety": 0.72, "rumination": 0.81, "avoidance": 0.33},
  "readiness_for_practice": 0.64,
  "coaching_hypotheses": ["thought_loop", "sleep_stress"],
  "confidence": 0.79,
  "candidate_constraints": ["avoid_long_protocol"]
}
```

### POST /v1/opportunity/score

**Request:**
```json
{
  "session_id": "uuid",
  "context_state": {},
  "recent_suggestions": [{"ts": "2026-02-25T10:00:00Z", "accepted": false}],
  "cooldowns": {"suggestion_cooldown_until": "2026-02-25T10:30:00Z"}
}
```

**Response:**
```json
{
  "opportunity_score": 0.74,
  "allow_proactive_suggest": true,
  "reason_codes": ["repeated_anxiety_signals", "prior_success_match"]
}
```

### POST /v1/practices/select

**Request:**
```json
{
  "context_state": {},
  "opportunity_score": 0.74,
  "top_k": 3
}
```

**Response:**
```json
{
  "ranked_practices": [
    {
      "practice_id": "grounding_5_4_3_2_1",
      "score": 0.86,
      "why": ["high_anxiety", "short_duration", "worked_before"]
    },
    {
      "practice_id": "socratic_questioning",
      "score": 0.68,
      "why": ["rumination_pattern"]
    }
  ]
}
```

### POST /v1/coach/decide

**Request:**
```json
{
  "context_state": {},
  "ranked_practices": [],
  "policy_flags": {"max_suggest_freq_ok": true}
}
```

**Response:**
```json
{
  "decision": "listen|explore|suggest|guide|answer",
  "selected_practice_id": "grounding_5_4_3_2_1",
  "style": "warm_directive",
  "must_ask_consent": true
}
```

## 5. FSM (2 уровня)

### Conversation FSM

```
FREE_CHAT ←→ EXPLORE ←→ PRACTICE_OFFERED → PRACTICE_ACTIVE ←→ PRACTICE_PAUSED
    ↑            ↑              ↑                  ↑                ↑
    └────────────┴──────────────┴──────────────────┴────────────────┘
                              CRISIS (из любого состояния)
```

| State | Event | Guard | Next State | Action |
|---|---|---|---|---|
| FREE_CHAT | message_received | risk=crisis | CRISIS | crisis_protocol |
| FREE_CHAT | message_received | decision=explore | EXPLORE | ask_clarifying |
| FREE_CHAT | message_received | decision=suggest | PRACTICE_OFFERED | send_offer |
| EXPLORE | new_info | decision=suggest | PRACTICE_OFFERED | send_offer |
| PRACTICE_OFFERED | user_accepts | consent=true | PRACTICE_ACTIVE | start_practice_run |
| PRACTICE_OFFERED | user_declines | - | FREE_CHAT | fallback_support |
| PRACTICE_ACTIVE | practice_paused | - | PRACTICE_PAUSED | save_checkpoint |
| PRACTICE_PAUSED | user_resumes | - | PRACTICE_ACTIVE | restore_checkpoint |
| PRACTICE_ACTIVE | practice_completed | - | FOLLOW_UP | summarize_and_plan |
| CRISIS | stabilized | risk < high | FREE_CHAT | safe_reentry |

### Practice FSM (внутри выбранной практики)

```
CONSENT → BASELINE → STEP_1 → ... → STEP_N → CHECKPOINT → ADAPT → WRAP_UP → FOLLOW_UP
                                       ↑           │
                                       └───────────┘ (корректировка)
```

| State | Event | Guard | Next State | Action |
|---|---|---|---|---|
| CONSENT | user_accepts | - | BASELINE | capture_baseline |
| BASELINE | baseline_done | - | STEP_1 | start_steps |
| STEP_n | user_response | on_track | STEP_n+1 | continue |
| STEP_n | user_response | confused | ADAPT | simplify_instruction |
| ADAPT | adapted | - | STEP_n | resume |
| STEP_n | distress_up | risk >= medium | CHECKPOINT | stabilization_prompt |
| CHECKPOINT | stabilized | - | STEP_n+1 | continue_safe |
| STEP_n | user_stop | - | WRAP_UP | partial_summary |
| STEP_last | finished | - | WRAP_UP | completion_summary |
| WRAP_UP | saved | - | FOLLOW_UP | next_recommendation |

## 6. Схема БД

| Таблица | Ключевые поля |
|---|---|
| users | id, created_at |
| user_profiles | user_id, readiness_score, preferred_style, language_pref, updated_at |
| sessions | id, user_id, started_at, language, conversation_state |
| messages | id, session_id, role, text, created_at, risk_level |
| mood_entries | id, user_id, session_id, mood_score, stress_score, created_at |
| practice_catalog | id, slug, title, targets[], contraindications[], duration_min, protocol_yaml, active |
| practice_steps | id, practice_id, step_order, step_type, content |
| practice_runs | id, user_id, session_id, practice_id, state, started_at, ended_at |
| practice_run_events | id, run_id, state_from, state_to, event, payload, created_at |
| practice_outcomes | id, run_id, baseline_mood, post_mood, self_report_effect, completed |
| decision_logs | id, session_id, context_state_json, decision, opportunity_score, selected_practice_id, latency_ms, cost |
| safety_events | id, session_id, detector, severity, action, created_at |

### Индексы

1. `messages(session_id, created_at DESC)`
2. `mood_entries(user_id, created_at DESC)`
3. `practice_outcomes(user_id, practice_id, created_at DESC)`
4. `decision_logs(session_id, created_at DESC)`
5. `safety_events(severity, created_at DESC)`

## 7. Логика ранжирования практик

### 7.1 Этапы ранжирования

1. **Hard Filter**: исключаем практики по contraindications, языку, доступности, лимитам частоты.
2. **Candidate Retrieval**: берём top-K по state_match и practice_targets.
3. **Personalized Scoring**: считаем итоговый балл по признакам + штрафам.
4. **Confidence Gating**: проверяем уверенность выбора перед проактивным предложением.
5. **Diversity/Repetition Control**: снижаем повторы, если недавно была та же техника.
6. **Final Pick**: 1 практика или 2 альтернативы при близких скорингах.

### 7.2 Формула

```
base_score = Σ(w_i * f_i)
final_score = base_score - penalties - uncertainty_penalty
```

Признаки:

| Признак | Вес | Описание |
|---|---|---|
| state_match | 0.35 | Релевантность состоянию (тревога/руминация/избегание) |
| historical_effect | 0.25 | Персональный эффект по прошлым запускам |
| readiness_fit | 0.15 | Соответствие текущей готовности пользователя |
| duration_fit | 0.15 | Подходит ли длина практики под текущий контекст |
| novelty | 0.10 | Не слишком ли часто предлагалась эта же техника |

Дополнительно: `dropout_risk_inverse` — вероятность, что пользователь дойдёт до конца.

### 7.3 Штрафы

- `contraindication_penalty` = block (не штраф, а полный запрет)
- `recent_decline_penalty`: если 1-2 последних предложения этой практики отклонены
- `overuse_penalty`: если практика использовалась слишком часто в коротком окне
- `fatigue_penalty`: если длинные практики предлагались недавно и completion низкий

### 7.4 Правила принятия решения

1. Если `opportunity_score < 0.60` — не предлагать практику, идти в listen/explore.
2. Если `top1_final_score < 0.58` — не делать жёсткое suggest, сначала explore.
3. Если `(top1 - top2) < 0.05` — предлагать 2 варианта на выбор.
4. Если `risk_level >= high` — обычный селектор отключается, только safety-flow.

### 7.5 Адаптивные веса по состоянию

- При высокой тревоге: увеличить вес `duration_fit` и коротких стабилизирующих техник.
- При руминации: увеличить вес `historical_effect` для когнитивных техник.
- При низкой готовности: увеличить вес `readiness_fit`, уменьшить сложность шага.

### 7.6 Обновление модели после каждой практики

1. Записывать `accepted`, `completed`, `post_mood_delta`, `self_report_effect`.
2. Пересчитывать `historical_effect` с байесовским сглаживанием (чтобы не переобучаться на 1 кейсе).
3. Обновлять персональные priors ежесессионно, глобальные веса пакетно (например, nightly job).

### 7.7 Что вернуть из селектора

`practice_id`, `final_score`, `confidence`, `reason_codes`, `blocked_by`, `alternative_ids`.

## 8. SQL: historical_effect и overuse_penalty

### PostgreSQL функция: calc_historical_effect

```sql
CREATE OR REPLACE FUNCTION public.calc_historical_effect(
  p_user_id uuid,
  p_practice_id uuid,
  p_m double precision DEFAULT 5.0,
  p_default_prior double precision DEFAULT 0.55,
  p_half_life_days double precision DEFAULT 30.0
)
RETURNS double precision
LANGUAGE sql
STABLE
AS $$
WITH scored_runs AS (
  SELECT
    pr.user_id,
    pr.practice_id,
    pr.ended_at,
    (
      0.50 * COALESCE(po.self_report_effect::double precision, 0.5) +
      0.35 * CASE
        WHEN po.post_mood IS NOT NULL AND po.baseline_mood IS NOT NULL THEN
          LEAST(
            GREATEST(((po.post_mood - po.baseline_mood + 4)::double precision) / 8.0, 0.0),
            1.0
          )
        ELSE 0.5
      END +
      0.15 * CASE WHEN po.completed THEN 1.0 ELSE 0.0 END
    ) AS run_effect
  FROM practice_runs pr
  JOIN practice_outcomes po ON po.run_id = pr.id
  WHERE pr.practice_id = p_practice_id
    AND pr.ended_at IS NOT NULL
),
global_prior AS (
  SELECT COALESCE(AVG(run_effect), p_default_prior) AS prior_mean
  FROM scored_runs
),
user_agg AS (
  SELECT
    COALESCE(SUM(
      run_effect *
      EXP(
        -LN(2.0) *
        (EXTRACT(EPOCH FROM (NOW() - ended_at)) / 86400.0) /
        GREATEST(p_half_life_days, 1.0)
      )
    ), 0.0) AS weighted_sum,
    COALESCE(SUM(
      EXP(
        -LN(2.0) *
        (EXTRACT(EPOCH FROM (NOW() - ended_at)) / 86400.0) /
        GREATEST(p_half_life_days, 1.0)
      )
    ), 0.0) AS effective_n
  FROM scored_runs
  WHERE user_id = p_user_id
)
SELECT
  LEAST(
    GREATEST(
      COALESCE(
        (
          ua.weighted_sum + GREATEST(p_m, 0.0) * gp.prior_mean
        ) / NULLIF(ua.effective_n + GREATEST(p_m, 0.0), 0.0),
        gp.prior_mean
      ),
      0.0
    ),
    1.0
  ) AS historical_effect
FROM user_agg ua
CROSS JOIN global_prior gp;
$$;
```

### PostgreSQL функция: calc_overuse_penalty

```sql
CREATE OR REPLACE FUNCTION public.calc_overuse_penalty(
  p_user_id uuid,
  p_practice_id uuid,
  p_cap double precision DEFAULT 0.35
)
RETURNS double precision
LANGUAGE sql
STABLE
AS $$
WITH usage AS (
  SELECT
    COUNT(*) FILTER (WHERE started_at >= NOW() - INTERVAL '7 days')  AS cnt_7d,
    COUNT(*) FILTER (WHERE started_at >= NOW() - INTERVAL '30 days') AS cnt_30d,
    MAX(started_at) AS last_used_at
  FROM practice_runs
  WHERE user_id = p_user_id
    AND practice_id = p_practice_id
)
SELECT
  LEAST(
    GREATEST(p_cap, 0.0),
    GREATEST((cnt_7d - 2), 0)::double precision * 0.08 +
    GREATEST((cnt_30d - 6), 0)::double precision * 0.05 +
    CASE
      WHEN last_used_at IS NULL THEN 0.0
      WHEN NOW() - last_used_at < INTERVAL '48 hours' THEN 0.12
      WHEN NOW() - last_used_at < INTERVAL '5 days'  THEN 0.06
      ELSE 0.0
    END
  ) AS overuse_penalty
FROM usage;
$$;
```

### Пример использования в ранжировании

```sql
SELECT
  p.id AS practice_id,
  0.35 * state_match
  + 0.25 * public.calc_historical_effect(:user_id, p.id)
  + 0.15 * readiness_fit
  + 0.15 * duration_fit
  + 0.10 * novelty
  - public.calc_overuse_penalty(:user_id, p.id) AS final_score
FROM practice_catalog p
WHERE p.active = true;
```

## 9. Политика проактивности

1. Не предлагать практику чаще 1 раза за 3 сообщения пользователя.
2. После 2 отказов подряд включать cooldown (24 часа / 1 сессия).
3. При `risk_level >= high` не предлагать обычные практики, только safety flow.
4. Всегда давать выход: "можем просто поговорить".

## 10. Safety требования

1. Crisis детектор работает до и после LLM.
2. Любой self-harm/violence триггер переводит в CRISIS.
3. Никаких директивных/обесценивающих формулировок в генерации.
4. В Output Safety Check проверка: тон, давление, медицинские/опасные советы.

## 11. Метрики и SLO

| Метрика | Что измеряет |
|---|---|
| `suggestion_acceptance_rate` | % принятых предложений практик |
| `practice_completion_rate` | % завершённых практик |
| `mood_delta_post_practice` | Изменение настроения после практики |
| `repeat_practice_effectiveness` | Эффективность повторных практик |
| `false_negative_crisis_rate` | Пропущенные кризисы |
| `overprompt_rate` | Частота навязчивых предложений |
| `p95_latency_ms` | Latency на 95-м перцентиле |
| `cost_per_session` | Стоимость за сессию |
