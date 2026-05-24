# Grow — Concept Document v2

> A personal health companion that learns, adapts, and stays curious about you.
> By Micke. May 2026.

---

## 1. What Is Grow?

Grow is a personal health app built around one idea: **sustainable change happens when the system adapts to the person, not the other way around.**

Most health apps assume a straight line from goal to result. Real life doesn't work that way. You get injured. Work gets intense. Motivation dips. The app that only understands "on track" and "off track" becomes irrelevant exactly when you need it most.

Grow is different. It tracks habits, body data, and life context — and uses that information to meet you where you are. When things go well, it helps you build on momentum. When things break down, it asks what happened and adjusts. The tone is never judgmental. It's curious.

**The tone is curious.** This is the leading design principle. Every interaction — every nudge, every question, every reflection — comes from a place of genuine interest in the person using the app. Not coaching. Not cheerleading. Curiosity. "You slept 4 hours and still hit your step target — what's going on today?" That's a more useful question than "Great job on your steps!"

### For Whom?

Grow is built for one person right now: Micke. The architecture supports multiple users, but the design decisions — the tone, the habits, the data sources — are shaped by one person's real needs. This isn't a limitation. It's a feature. A tool built for everyone helps no one. A tool built for one person, deeply and honestly, might eventually help many.

### Core Data Sources

- **Oura Ring** — sleep, steps, HRV, readiness, heart rate, workouts
- **Google Calendar** — meeting density, free gaps, context for nudges
- **Manual logging** — weight, meals, fasting, sweet cravings, exercise, reflections
- **Local AI model** — pattern recognition across all data (Ollama + Ministral 3B on Raspberry Pi)

---

## 2. The Three Phases

Grow organizes the user's journey into three phases. These aren't sequential stages you graduate from — they're states you move between as life changes. The app detects which phase fits and adjusts its behavior accordingly.

### Phase 1: Build Routine

**When:** Starting out, or restarting after a break.

The goal is not results — it's consistency. Phase 1 focuses entirely on establishing a small set of daily habits and making them stick. The app is gentle, the targets are low, and every small action is celebrated.

**Key behaviors:**
- Micro-habit emphasis. The smallest meaningful action counts: a 10-minute walk, logging one meal, going to bed before midnight. The system rewards showing up, not performance.
- Low thresholds. Step targets start modest. IF windows are flexible. Training frequency is suggested, not demanded.
- Morning notification. A single daily touchpoint: "Good morning. You slept 7h 12m. Your eating window opens at 11:00. Light calendar today — good day for a walk?" Short, warm, data-informed.
- Garden grows easily. Seeds are generous in Phase 1. The visual garden should grow visibly in the first week. Early momentum matters.

**Transition to Phase 2:** Triggered when core habits show consistency over 2–3 weeks (e.g., IF adherence >70%, steps >60% of target, logging happening most days). The app notices and asks: "You've been consistent for two weeks. Want to raise the bar a little?"

### Phase 2: Harvest

**When:** Habits are established. The user is ready for results.

Phase 2 shifts focus from "did you show up?" to "how are you progressing?" Targets tighten. The app starts surfacing trends and patterns. The AI becomes more active, correlating sleep, activity, nutrition, and mood.

**Key behaviors:**
- Tighter targets. Step goals increase. IF adherence expectations rise. Training consistency matters more.
- Trend visibility. Weight trend lines, sleep score patterns, step averages over time. The dashboard shifts from daily snapshot to weekly/monthly trajectory.
- AI insights activate. The local model starts generating observations: "Your sleep drops on days with 4+ meetings. Could you block 30 minutes before bed on heavy days?" These come from real data, not generic advice.
- Plate model nutrition. Meals tracked against the plate model (tallriksmodellen): half vegetables, quarter protein, quarter carbs. Not calorie counting — proportional awareness. The app asks "How did your plate look today?" with a simple visual selector, not a food database.
- Weekly reflection. A structured but brief weekly check-in (see section 5).

**Transition to Phase 3:** Triggered by life disruption — injury, sustained stress, travel, illness. The app detects this through data patterns (sudden drop in activity, missed logging days, sleep quality decline) or the user can flag it manually.

### Phase 3: Adapt

**When:** Something broke the routine. Injury, work crisis, illness, life event.

This is where Grow is fundamentally different from other health apps. Phase 3 doesn't just pause — it actively helps the user navigate the disruption and find a path back.

**Key behaviors:**
- Immediate acknowledgment. "It looks like things have changed this week. That's okay. Want to tell me what's going on?" No guilt. No streak-breaking drama.
- Structured disruption tracking. The user can log what happened: injury (type, severity, timeline), work stress (duration estimate), illness, travel, or "just life." Each disruption type triggers adapted behavior.
- Adapted programs. Knee injury? The app shifts from step targets to upper-body exercises and swimming suggestions. Work stress? It reduces notifications and emphasizes sleep and recovery. The adapted program has a timeline: "Let's focus on recovery for 2 weeks, then reassess."
- Micro-habits as anchor. Even in Phase 3, the smallest habits remain. "Can you do one thing today? A 5-minute stretch. Logging your sleep. Drinking water." The garden doesn't die in Phase 3 — it slows down, but it doesn't stop.
- Return path. When the disruption eases, the app gradually reintroduces Phase 1 behaviors. Not a hard reset — a gentle ramp. "Your knee is feeling better? Let's start with short walks this week."

---

## 3. The Curious Tone

The tone is the product. Not the features, not the data, not the gamification — the tone. Everything in Grow flows from this principle: **the app is genuinely curious about the person using it.**

### What Curious Means

Curious means asking questions instead of making statements. "You had a sweet after lunch — was it a craving or a social thing?" is more useful than "You had a sweet after lunch." The first invites reflection. The second invites guilt.

Curious means noticing patterns without judging them. "You tend to skip IF on Mondays. Is Monday different for you?" Not "You broke your fast on Monday again."

Curious means celebrating the interesting, not just the good. "You slept 5 hours but your HRV is higher than usual — your body is resilient today" is more engaging than silence on a bad sleep night.

### What Curious Doesn't Mean

Curious doesn't mean passive. The app still nudges, suggests, and encourages. It just does it from a place of interest rather than authority.

Curious doesn't mean chatty. Messages are short. One question at a time. The app respects that the user has a life outside of it.

Curious doesn't mean therapeutic. Grow is not a therapist. It doesn't ask "How does that make you feel?" It asks "What happened?" and "What worked?" — practical, forward-looking questions.

### Tone Examples

| Situation | Generic app | Grow |
|-----------|------------|------|
| Missed step target | "You didn't reach your goal today." | "Quieter day. Your calendar was packed — makes sense." |
| Sweet logged | "Snack logged. +150 cal." | "Afternoon sweet. Want to note what was going on?" |
| Great sleep | "Sleep score: 92!" | "Deep sleep was 2h 10m last night — that's your best this week." |
| Training skipped | "You missed your workout." | "No session today. Still 3 days until the weekend — time to fit one in?" |
| Returned after break | "Welcome back! You lost your streak." | "Hey. Been a while. How are things?" |
| Injury logged | — | "Got it. What can you still do comfortably?" |

---

## 4. Micro-Habits

Micro-habits are the engine of Grow. They're the smallest meaningful actions — things so small they're almost impossible to skip. They serve two purposes: they build consistency in Phase 1, and they maintain connection in Phase 3.

### How They Work

Each day, the app suggests 1–3 micro-habits based on context. These are drawn from a pool that adapts to the user's phase, current data, and any active disruptions.

**Examples by category:**

- **Movement:** Take a 10-minute walk. Stand up and stretch. Walk to the end of the street and back.
- **Nutrition:** Eat one meal with vegetables filling half the plate. Drink a glass of water before your first coffee. Skip the second serving.
- **Recovery:** Be in bed by 23:00. Put the phone down 30 minutes before sleep. Take 5 deep breaths.
- **Awareness:** Log one meal honestly. Note what triggered a craving. Write one sentence about how you feel.
- **Training (adapted):** 10 kettlebell swings. One set of push-ups. 15 minutes of cycling (if knee allows).

### Rewards

Completing a micro-habit earns seeds — the same currency that grows the garden. Micro-habits give fewer seeds than full habits (1 seed vs. 3–4), but they're available every day regardless of phase. This means:

- In Phase 1, micro-habits are the primary seed source. The garden grows from small actions.
- In Phase 2, they supplement full habits. A training day might earn 5 seeds from training + 1 from a micro-habit.
- In Phase 3, they're often the only seed source. The garden slows but doesn't stop.

### The Psychology

The point of micro-habits isn't the action itself — it's the identity reinforcement. Doing a 10-minute walk when you have a knee injury isn't about fitness. It's about staying the kind of person who moves. Logging one meal during a stressful week isn't about nutrition tracking. It's about maintaining the connection to the system.

The app frames this explicitly when needed: "One small thing today keeps the garden alive."

---

## 5. Weekly Reflection

Once a week (Sunday evening or Monday morning — user chooses), Grow presents a brief structured reflection. This replaces daily journaling or evening check-ins, which feel like obligations. Weekly is frequent enough to surface patterns, infrequent enough to feel special.

### Structure

The reflection has three parts, each taking about one minute:

**1. The Week in Numbers**
A visual summary of the week's data. Not raw numbers — contextual highlights chosen by the AI:

- "You averaged 7,200 steps this week, up from 6,400 last week."
- "Sleep quality dipped mid-week — Wednesday and Thursday were below your baseline."
- "3 out of 5 IF days completed. That's consistent with your last month."
- "You logged 2 sweets. Both were afternoons after short sleep."

The AI selects 3–4 data points that tell a story. Not a dump of every metric.

**2. Smart Questions**
Based on the week's data, the AI generates 2–3 questions. These are the curious tone at its most powerful:

- "Your steps were highest on the days you had fewer meetings. Do you think there's a connection?"
- "You skipped training on Thursday but did a long walk on Saturday. Is the schedule shifting?"
- "Two sweets this week, both after short sleep. Do you notice that pattern?"

The user can answer briefly or skip. Answers feed the AI's understanding for future insights.

**3. Next Week**
A forward-looking micro-plan based on the calendar and recent patterns:

- "Next week has a lighter Tuesday — maybe a good training day?"
- "You have a full day Thursday. Let's not expect much movement that day."
- "Your weight trend has been flat for 10 days. That's normal — keep going."

The tone here is collaborative: "Here's what I see, here's what I suggest, you decide."

### What It's Not

The weekly reflection is not an evaluation. There are no grades, no "this week was a B+." It's not a confession — there's no "what went wrong" section. The emphasis is on what happened (data), what's interesting (patterns), and what's next (suggestions).

---

## 6. Nutrition: The Plate Model

Grow doesn't count calories. Calorie counting is effective but unsustainable for most people. Instead, Grow uses the plate model (tallriksmodellen) — a Nordic nutritional guideline based on proportions rather than quantities.

### The Plate

Each meal is a plate divided into sections:

- **Half: Vegetables and greens** — salad, cooked vegetables, root vegetables
- **Quarter: Protein** — meat, fish, eggs, legumes, tofu
- **Quarter: Carbohydrates** — rice, pasta, potatoes, bread

### How It Works in Grow

At meal time (within the IF eating window), the user gets a gentle prompt: "How did your plate look?" The interface shows a simple plate graphic. The user taps to indicate proportions: "mostly balanced," "heavy on carbs," "skipped vegetables," or "great plate." Four taps, no typing required.

Over time, the AI spots patterns: "You tend to skip vegetables at lunch but nail it at dinner. What's different?" This is the curious tone applied to nutrition.

### Integration with IF

The plate model complements intermittent fasting naturally. The eating window (default 11:00–19:00) defines when you eat. The plate model guides what you eat. Together they cover timing and composition without the overhead of food logging apps.

The app tracks:
- IF adherence (did you stay within the window?)
- Plate quality (rough proportional assessment)
- Sweet/snack awareness (the existing logging system)

This gives a complete nutritional picture with minimal logging effort.

---

## 7. Injury and Disruption Tracking

Life isn't linear. A health app that doesn't understand disruptions is a health app that gets uninstalled when you need it most.

### Logging a Disruption

When the user (or the AI) identifies a disruption, Grow opens a structured entry:

**Type:** Injury / Work stress / Illness / Travel / Personal / Other

**For injuries:**
- Body part and nature (knee pain, back strain, etc.)
- Severity (mild / moderate / significant)
- Can still do: checkboxes for walking, cycling, swimming, upper body, stretching
- Estimated recovery: 1 week / 2 weeks / 1 month / unknown
- Medical guidance: yes/no (the app adjusts caution level accordingly)

**For work stress:**
- Duration estimate: this week / next 2 weeks / ongoing / unknown
- Impact on: sleep / energy / time / motivation (multi-select)
- One thing you can still do? (free text, optional)

**For all types:**
- The app creates a timeline. Day 1 of disruption, with a planned reassessment point.
- Adapted targets are set immediately: reduced step goals, relaxed IF expectations, micro-habits only.
- The garden enters a "winter" visual mode — still alive, growing slowly, but clearly in a different season.

### Recovery Arc

Disruptions have a lifecycle:

1. **Acute** (days 1–3): Maximum flexibility. Micro-habits only. Empathetic tone. "Just take care of yourself."
2. **Adaptation** (days 4–14): Adjusted program kicks in. Alternative exercises for injuries. Reduced targets for stress. "Here's what we can work with."
3. **Reintegration** (day 14+): Gradual return to normal. The app suggests stepping up one habit at a time. "Your knee is better? Let's try a short walk today and see how it feels."
4. **Resolved**: Back to Phase 1 or Phase 2, depending on how long the disruption lasted. If more than 3 weeks, always restart at Phase 1 for a week.

### Why This Matters

Most health apps treat disruptions as failure. Streak broken. Progress lost. Start over. Grow treats disruptions as data. "You were injured for two weeks and maintained your sleep habits throughout. That's remarkable." The garden remembers. The AI remembers. Nothing is lost.

---

## 8. The Garden

The visual garden is Grow's signature. Every good choice — a walk, a fasted morning, a good night's sleep, a training session, choosing not to have a sweet — plants a seed. Seeds grow a living CSS scene.

### Five Elements

| Element | Habit | What Grows |
|---------|-------|------------|
| Meadow | Steps & movement | Grass, wildflowers |
| Oak | IF adherence | Tree, stronger trunk, fuller crown |
| Pond | Sleep quality | Water, reflection, lilies |
| Stones | Training | Stone path, stepping stones |
| Path | Awareness & logging | Winding path, lanterns |

Each element has 10 growth stages. The visual scene evolves from bare ground to a rich Scandinavian forest garden. The aesthetic is hand-drawn, warm, seasonal.

### Seeds Per Day

A good day earns 8–12 seeds. A minimal day earns 2–3. A disruption day with one micro-habit earns 1. The point is: you can always earn at least one seed. The garden never completely stops.

**Streak bonus:** 7 consecutive days of any logging earns +5 bonus seeds. This rewards showing up, not perfection.

### Seasons and Weather

The garden reflects real conditions:

- **Phase 1:** Spring. Everything is budding. Growth is fast and visible.
- **Phase 2:** Summer. Full bloom. The garden is lush and rewarding.
- **Phase 3:** Autumn/Winter. The garden doesn't die — it goes dormant. Warm colors, bare branches, but still beautiful. A reminder that rest is part of growth.

---

## 9. The Morning View: Dashboard Design

The dashboard is the daily touchpoint. It's the moment the person decides whether to engage or close the app. This means it has one job: make engagement feel effortless and worthwhile.

### Design Principle: Garden Hero, Interaction Queen

The garden is the emotional center — the first thing you see, filling the screen. Not a card among twelve. The whole view. You open Grow and you see your garden. It's a little different from yesterday. Something grew. That's the moment.

But emotion without action is passive. The interaction layer — the status sentence, the micro-habits, the focus question — is what turns a glance into a choice. The garden draws you in. The interaction gives you something to do.

### The Morning View (Default State)

The dashboard shows exactly five things, in this order:

**1. The Garden (hero)**
Full-width visual scene. Phase indicator visible as a subtle label or arc: "Building routine · Week 3" or "Adapting · Day 5." A seed counter or "+8 seeds yesterday" animation that gives concrete progress signal. The garden visual sets mood — but the phase indicator and seed count are the legible progress signals.

**2. Status Sentence**
One line. Composed from yesterday's data, today's calendar, active disruptions, and the weekly focus. This is the voice of the app — the curious tone made concrete in a single sentence.

Rule-based examples (until AI takes over):
- "9,200 steps yesterday, IF on track. Light calendar today — good for kettlebells?"
- "Rough sleep last night, full schedule. Small actions count today."
- "Knee's healing, day 8. Walking and upper body — that's plenty."
- "Been a few days. Pick one thing and let's go."
- "Third week of consistent steps. Something's clicking."

When Ministral 3B runs, this slot gets an AI-composed sentence from the Nudge Composer agent. The UI doesn't change at all — the intelligence behind the sentence just deepens.

**3. Weekly Focus**
A single highlighted area: "This week: steps consistency" or "This week: sleep before midnight." Chosen by the user weekly (the app suggests based on data, the user confirms). Everything else in the UI takes a back seat to this focus.

If no focus is set, the app gently asks: "What matters most this week?" with 3–4 data-informed options to tap.

The focus concept solves two problems: it reduces cognitive load (you know what to care about today), and it gives the AI a lens for all its output (patterns, nudges, and reflections all orient around the focus).

**4. Today's Micro-Habits**
Two or three contextual suggestions. One-tap completion. Filtered by disruptions, phase, and weekly focus.

**5. Quick Log**
IF status (tap to confirm), sweet/skip buttons. Minimal, expandable.

That's it. Five elements. Thirty seconds to engage.

### Progressive Disclosure: Everything Else

All detailed metrics — sleep breakdown, step history, exercise log, weight trend, calendar view — live one tap deeper. Not hidden. Not removed. Just not competing for the morning view.

These detailed views surface automatically in exactly one case: **anomalies.** If a metric deviates significantly from the user's recent average, it appears as a card on the dashboard. "Sleep score 45 — that's unusual for you" or "Already at 9,000 steps by 2 PM — on a roll." Anomalies are interesting. Interesting earns a place on the morning view. Normal doesn't.

The anomaly threshold is personal: calculated from the user's own rolling 14-day average. What's unusual for Micke isn't unusual for someone else. This is the curious tone applied to data display: the app notices what's different, not what's expected.

### Notifications and Nudges

**Morning nudge (9:00 AM):** If the user hasn't opened the app today, send a push notification. Content: yesterday's highlight + today's focus. "Your oak grew yesterday — 5 days of IF. What matters today?" One tap opens the morning view.

**Technical path:** Web Push API via service worker. The Pi has HTTPS (Caddy + Tailscale certs), which is the prerequisite. A cron job at 9:00 checks `last_visited` and triggers a push via the web-push Python library using stored VAPID keys and the browser's push subscription.

**Inactivity nudge (after 2–3 days):** The tone shifts from "here's your data" to "wondering about you." "It's been a few days. Everything okay, or is something going on?" with a one-tap path to logging a disruption. This turns silence from a failure state into useful information.

**No evening notifications.** Evenings are for rest. If the user opens the app in the evening, the view is calm: "Good day. +8 seeds. Rest well." No prompts, no logging suggestions.

### Phase-Adaptive Dashboard

The morning view adapts to the current phase:

**Phase 1 (Build Routine):** Garden in spring colors. Status sentence focuses on showing up, not performance. Micro-habits are generous and simple. Anomaly cards are rare — the user is still establishing baselines. Focus suggestions are about consistency: "This week: log something every day."

**Phase 2 (Harvest):** Garden in full summer. Status sentence references trends and patterns. Anomaly cards appear when the AI spots something interesting. Focus suggestions target improvement: "This week: hit step target 5 out of 7 days."

**Phase 3 (Adapt):** Garden in autumn/winter mode — warm, quiet, still alive. Status sentence acknowledges the disruption and what's still possible. Micro-habits filter to what the disruption allows. Focus is about maintaining connection: "This week: one small thing each day."

### Why This Design

The previous dashboard had twelve cards: garden, calendar, movement, sleep, IF, exercise, nudge, weight, quick log, insight, micro-habits, streaks. Each individually useful. Together, they created a report — not a morning moment. The cognitive load contradicted the curious tone.

The redesigned view asks: "What does this person need to see right now?" and shows only that. The answer depends on the phase, the data, and the focus. A person in Phase 1 needs encouragement and simplicity. A person in Phase 2 needs trends and insight. A person in Phase 3 needs gentleness and connection.

This aligns with the core behavior science insight: people succeed when they change one or two things at a time, not six. The focus system operationalizes this. The progressive disclosure enforces it. The garden makes it feel good.

---

## 10. Local AI: Architecture

All intelligence in Grow runs locally on the Raspberry Pi 5. No data leaves the device. This is a core design principle — a health app that sends your sleep, weight, and eating habits to the cloud is a health app you can't fully trust.

### Stack

- **Hardware:** Raspberry Pi 5 (4 GB RAM)
- **Runtime:** Ollama — an open-source local inference server. American-built, well-maintained, runs on ARM.
- **Model:** Ministral 3B — a 3-billion parameter model from Mistral AI (Paris, France). Compact but capable at focused tasks. At Q4_K_M quantization (~2 GB), it fits comfortably in 4 GB RAM alongside the OS, Flask, and SQLite. EU-based company, open weights.
- **Embeddings:** nomic-embed-text via Ollama (~275 MB). Used for semantic search over historical data — weekly reflections, food log notes, disruption entries. Loaded sequentially with Ministral 3B, not simultaneously, to stay within memory.
- **Vector storage:** sqlite-vec — a SQLite extension for vector similarity search. Zero extra memory overhead since Grow already uses SQLite. Embeddings live alongside the rest of the data. No separate database process needed, unlike heavier options like Milvus or ChromaDB.
- **Integration:** Ollama HTTP API from Flask. The AI is a service, not embedded in the app. Direct API calls — no LangChain or other orchestration frameworks. The agent pipeline is simple enough that the overhead of a framework isn't justified.

### The Agent Network

Rather than one monolithic AI prompt trying to do everything, Grow uses a network of focused agents — small, sequential calls to the local model, each with a specific job:

**Agent 1: Data Summarizer**
Input: Raw data from the last 7 days (sleep, steps, IF, meals, training, calendar).
Output: Structured summary in natural language. "This week: 5/7 days fasted, average 7,100 steps, two short-sleep nights (Wed/Thu), one training session, three sweets."

**Agent 2: Pattern Finder**
Input: The summary from Agent 1 + historical summaries from the last 4 weeks.
Output: Patterns and correlations. "Sweet cravings correlate with short sleep (3 of 4 sweets this month were after <6h sleep). Step count drops on 4+ meeting days."

**Agent 3: Question Generator**
Input: Patterns from Agent 2 + current phase + any active disruptions.
Output: 2–3 curious questions for the weekly reflection. "Your sweets this week both followed short nights. Do you notice the connection?"

**Agent 4: Nudge Composer**
Input: Today's data + calendar + patterns + phase.
Output: The daily nudge message. Context-aware, phase-appropriate, personality-consistent.

**Agent 5: Adaptation Advisor** (Phase 3 only)
Input: Disruption details + user's "can still do" list + historical preferences.
Output: Adapted weekly plan. "For your knee recovery: swimming Mon/Wed, upper body Thu, walks as tolerated. Step target reduced to 4,000."

### Why Sequential Agents?

A single prompt with all context would be long, slow, and unreliable on a 3B model. Sequential agents let each call be focused: clear input, clear task, clear output. Each agent's output is structured (JSON or simple text), making it easy to chain. If one agent fails or gives poor output, the pipeline handles it gracefully — the nudge might be slightly generic, but the app doesn't break.

This architecture also means each agent can be tested and improved independently. The pattern finder can get better prompts without touching the nudge composer.

The 3B model is well-suited to this design. Each agent does one thing: summarize numbers, find a pattern, write a sentence. These are focused tasks with structured inputs and short outputs — exactly where smaller models perform reliably. The trade-off versus a 7B model is less nuanced reasoning, but within the agent network that's compensated by giving each agent a narrow, well-defined job.

### Embedding-Augmented Retrieval

The Pattern Finder (Agent 2) benefits from semantic search over historical data. Rather than passing four weeks of raw summaries into each prompt, relevant history is retrieved via vector similarity:

1. Weekly summaries, food log notes, and disruption entries are embedded using nomic-embed-text and stored in sqlite-vec.
2. When the Pattern Finder runs, the current week's summary is embedded and used to retrieve the most similar historical entries.
3. Only the relevant history is included in the prompt, keeping it short and focused — critical on a 3B model where context window and reasoning quality both benefit from concise input.

This is not a full RAG chatbot. It's targeted retrieval to make one specific agent smarter without bloating its prompt.

### Memory Management

With 4 GB total RAM, memory discipline matters. The OS and Flask/SQLite use roughly 500 MB–1 GB. Ministral 3B at Q4_K_M uses ~2 GB. That leaves a comfortable margin, but not room for running the LLM and embedding model simultaneously.

The pipeline handles this by loading models sequentially. Embedding happens first (embed this week's data, retrieve similar history), then nomic-embed-text is unloaded and Ministral 3B is loaded for the agent calls. Ollama handles model loading/unloading automatically — if you request a different model, it swaps. The full pipeline runs once per day (morning notification) and once per week (reflection), so the swap cost is negligible.

### Privacy

Nothing leaves the Pi. The model runs in RAM. Prompts and responses are transient — only the structured outputs (summaries, patterns, insights) are stored in the database for future reference. Raw model conversations are discarded after processing. Embeddings are stored locally in SQLite alongside all other data.

The user's data stays in their house, on their device, processed by an open-source model. This is the strongest privacy guarantee possible.

---

## 11. A Day in Grow

Here's what a typical day looks like across the three phases:

### Phase 1 Day (Building Routine)

**07:30** — Morning notification: "Good morning. You slept 6h 48m — not your best, but deep sleep was solid. Eating window opens at 11:00. You have a light day — good for a walk after lunch."

**11:15** — User opens the app, eats lunch. Taps "How was your plate?" → "Mostly balanced." One tap.

**14:00** — After-lunch micro-habit prompt: "A 10-minute walk would grow your meadow. You have a gap until 15:00."

**15:30** — User logs a sweet. The app asks: "Afternoon sweet — want to note what was going on?" User types "tired after meeting" or skips.

**19:00** — Eating window closes. IF logged automatically.

**21:00** — No evening check-in. The app is quiet.

### Phase 2 Day (Harvesting)

Same structure, but:
- Morning notification includes trend context: "Your 7-day step average is 7,800 — almost at 8,000."
- Plate model tracking is more detailed: "You've had vegetables at dinner every day this week but not at lunch. Interesting."
- AI insight appears on dashboard: "On days when you walk at lunch, you tend to sleep 20 minutes longer. Worth noting."

### Phase 3 Day (Adapting — Knee Injury, Day 5)

**07:30** — "Morning. Day 5 of knee recovery. You slept well — 7h 22m. Today's micro-habit: 5 minutes of upper body stretching. That's enough."

**12:00** — User opens app. Dashboard shows adapted targets: step goal reduced, training replaced with "gentle movement." The garden is in autumn mode — warm, quiet, still growing.

**18:00** — "How's the knee feeling today?" Simple scale: worse / same / slightly better. This builds the recovery timeline.

---

## 12. Motivation Philosophy

Grow is built on three principles that guide every design decision. They come from Nordic cultural wisdom — practical, balanced, and humane — but they're expressed through behavior, never through labels or slogans.

### Perseverance

The belief that you can keep going, even when it's hard. Not through force of will, but through systems that make persistence the path of least resistance. Micro-habits embody this: the bar is so low that "doing something" is always possible. The garden embodies this: it never dies, it only slows. Perseverance isn't dramatic. It's quiet. It's logging one meal during a terrible week and knowing that matters.

### Moderation

The rejection of extremes. Grow doesn't celebrate crushing your goals — it celebrates balance. A 10,000-step day isn't twice as good as a 5,000-step day. A perfect week of IF isn't better than a week with one slip and honest reflection. The plate model is moderation made visual: not "eat less," but "eat proportionally." The system actively discourages overtraining and under-sleeping in pursuit of other metrics.

### Enjoyment

The recognition that health isn't sacrifice. Logging a sweet isn't a confession — it's awareness. Having a glass of wine on Friday isn't a failure. Choosing to rest instead of train isn't weakness. Grow tracks enjoyment as data, not sin. "You had two sweets this week, both in social situations. That looks like enjoyment, not a pattern problem."

These three principles create a system that's firm without being harsh, flexible without being permissive, and honest without being cruel.

---

## 13. Technical Summary

### Current Stack
- **Backend:** Python 3.12, Flask 3.1, SQLAlchemy, SQLite
- **Frontend:** Jinja2 templates, vanilla CSS + JS, mobile-first
- **APIs:** Oura API v2 (PAT), Google Calendar (OAuth2 read-only)
- **Security:** Flask-WTF CSRF, security headers, OAuth state validation
- **Deployment:** Raspberry Pi 5 (hallonpaj1), systemd, LAN access at 192.168.50.16:8080
- **Source:** github.com/mickhinds/grow (public)

### Built
- **Tailscale + Caddy** — secure HTTPS remote access via hallonpaj1.tail745dc7.ts.net
- **Micro-habit engine** — rule-based selection, 24 habits, context-aware, 1 seed per completion
- **Disruption tracking** — structured logging (injury, stress, illness, travel, mental health), status lifecycle, dashboard banner
- **Contextual greeting** — time-of-day + data-informed (sleep, readiness, calendar)
- **Reset system** — three levels (recalibrate, start over, total reset) in Settings
- **Day counter** — based on user.start_date, resets with start-over/recalibrate

### Planned Additions
- **Dashboard redesign** — garden-hero morning view, status sentence, weekly focus, progressive disclosure (see section 9)
- **Weekly focus system** — user-chosen weekly priority, data-informed suggestions
- **Status sentence engine** — rule-based → AI-composed daily one-liner
- **Anomaly detection** — surface metrics only when they deviate from personal baseline
- **Web Push notifications** — 9 AM morning nudge, inactivity nudge, via service worker + VAPID
- **Ollama + Ministral 3B** — local AI on the Pi, with nomic-embed-text for semantic retrieval via sqlite-vec
- **Plate model UI** — simple meal proportion selector
- **Weekly reflection engine** — data summary + AI questions + next-week plan

### Database Additions Needed
- `WeeklyReflection` — answers, generated insights, next-week plan
- `MealLog` — plate model assessments (replaces or extends FoodLog)
- `AIInsight` — stored agent outputs for the dashboard
- `Phase` tracking — current phase per user, transition history
- `User.weekly_focus` — current focus area and week number
- `PushSubscription` — browser push subscription data per user

---

## 14. What's Not in Scope (Yet)

These ideas came up during design but are deferred:

- **Social features** — sharing progress, group challenges, accountability partners. Interesting but premature. Get the single-user experience right first.
- **Native mobile app** — the web app works well on mobile. A native app would add push notifications and offline support, but it's a different project.
- **Third-party integrations** — Apple Health, Google Fit, Withings, etc. Oura is the primary data source for now. Others can come later through the same sync pattern.
- **Conversational UI** — a chat interface instead of cards and buttons. This is on the backlog but depends on the local AI being reliable enough for free-form conversation.
- **Commercial multi-user** — the architecture supports it (user_id on all tables), but the design is intentionally personal right now.

---

## 15. The Name

Grow. A garden grows. A person grows. Habits grow. Understanding grows. The name works on every level. It's short, warm, and universal. It's not a medical term. It's not a fitness brand. It's a verb — an invitation.

---

*This document serves as the design foundation for Grow's continued development. It's a living document — updated as the app evolves and as Micke's needs change. The principles don't change. The implementation always will.*
