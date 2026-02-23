# Token Cost Guardrails & Warning System

## Context
The assistant's `get_missing_assignments` tool was called 5-6 times per query (once per period) with ~25K char responses each, costing $1+ for a single question. The root data issue is fixed (new all-periods mode returns ~4K in one call), but there are no guardrails to prevent future expensive queries from any tool. This plan adds a cost-aware system that warns the teacher and caps runaway tool loops.

## Files

| File | Action |
|------|--------|
| `backend/routes/assistant_routes.py` | **MODIFY** — add tool response truncation, per-round cost check, reduce max_rounds, emit `cost_warning` SSE event |
| `frontend/src/components/AssistantChat.jsx` | **MODIFY** — handle `cost_warning` event, color-code per-message cost, show toast warning |

---

## Step 1: Backend — `assistant_routes.py`

### Edit 1A: Add cost constants (after line 234)

**Location:** After `OPENAI_TTS_VOICES = [...]` on line 234

```python
# --- FIND (line 234): ---
OPENAI_TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]

# --- REPLACE WITH: ---
OPENAI_TTS_VOICES = ["alloy", "ash", "coral", "echo", "fable", "nova", "onyx", "sage", "shimmer"]

# Token cost guardrails
MAX_TOOL_RESPONSE_CHARS = 8000   # Truncate tool results larger than this
COST_WARNING_THRESHOLD = 0.25    # Warn teacher when per-query cost exceeds this
MAX_TOOL_ROUNDS = 3              # Max tool loop iterations (was 5)
```

### Edit 1B: Reduce max_rounds (line 1123)

**Location:** Line 1123 inside `generate()`

```python
# --- FIND (line 1123): ---
        max_rounds = 5

# --- REPLACE WITH: ---
        max_rounds = MAX_TOOL_ROUNDS
```

### Edit 1C: Add per-round cost check (line 1124)

**Location:** Line 1124, change the loop variable and add cost check inside

```python
# --- FIND (lines 1123-1126): ---
        max_rounds = MAX_TOOL_ROUNDS
        for _ in range(max_rounds):
            try:
                full_response_text = ""

# --- REPLACE WITH: ---
        max_rounds = MAX_TOOL_ROUNDS
        for _round_idx in range(max_rounds):
            try:
                # Per-round cost check — warn and stop if getting expensive
                if _round_idx > 0 and total_input_tokens > 0:
                    _pricing = MODEL_PRICING.get(active_model, {"input": 0, "output": 0})
                    _est_cost = (total_input_tokens * _pricing["input"] + total_output_tokens * _pricing["output"]) / 1_000_000
                    if _est_cost > COST_WARNING_THRESHOLD:
                        yield f"data: {json.dumps({'type': 'cost_warning', 'estimated_cost': round(_est_cost, 4), 'rounds_used': _round_idx})}\n\n"
                        break  # Stop the tool loop — too expensive

                full_response_text = ""
```

### Edit 1D: Truncate large tool responses (after line 1376)

**Location:** Line 1376, after `result_str = json.dumps(result)`

```python
# --- FIND (lines 1376-1378): ---
                    result_str = json.dumps(result)

                    yield from _flush_audio_queue()

# --- REPLACE WITH: ---
                    result_str = json.dumps(result)
                    if len(result_str) > MAX_TOOL_RESPONSE_CHARS:
                        result_str = result_str[:MAX_TOOL_RESPONSE_CHARS] + '... [TRUNCATED from ' + str(len(result_str)) + ' chars. Use a more specific query for full details.]'

                    yield from _flush_audio_queue()
```

### Edit 1E: Add high_cost flag to final cost event (lines 1447-1452)

**Location:** Lines 1447-1452, the cost summary emission

```python
# --- FIND (lines 1447-1452): ---
        if total_input_tokens > 0 or total_tts_chars > 0:
            cost_info = _record_assistant_cost(
                total_input_tokens, total_output_tokens,
                active_model, total_tts_chars
            )
            yield f"data: {json.dumps({'type': 'cost', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens, 'tts_chars': total_tts_chars, **cost_info})}\n\n"

# --- REPLACE WITH: ---
        if total_input_tokens > 0 or total_tts_chars > 0:
            cost_info = _record_assistant_cost(
                total_input_tokens, total_output_tokens,
                active_model, total_tts_chars
            )
            if cost_info.get("total_cost", 0) > COST_WARNING_THRESHOLD:
                cost_info["high_cost"] = True
            yield f"data: {json.dumps({'type': 'cost', 'input_tokens': total_input_tokens, 'output_tokens': total_output_tokens, 'tts_chars': total_tts_chars, **cost_info})}\n\n"
```

---

## Step 2: Frontend — `AssistantChat.jsx`

### Edit 2A: Handle `cost_warning` SSE event (after line 358)

**Location:** After the `audio_chunk` handler (line 358), before the `cost` handler (line 359)

```javascript
// --- FIND (lines 355-359): ---
            } else if (event.type === 'audio_chunk') {
              if (voiceModeRef.current && event.audio) {
                voice.enqueueAudioChunk(event.audio)
              }
            } else if (event.type === 'cost') {

// --- REPLACE WITH: ---
            } else if (event.type === 'audio_chunk') {
              if (voiceModeRef.current && event.audio) {
                voice.enqueueAudioChunk(event.audio)
              }
            } else if (event.type === 'cost_warning') {
              if (addToast) addToast(
                'High token usage: ~$' + event.estimated_cost.toFixed(4) + ' after ' + event.rounds_used + ' tool rounds. Query stopped to save cost.',
                'warning',
                8000
              )
            } else if (event.type === 'cost') {
```

### Edit 2B: Add toast on high final cost (line 368)

**Location:** Line 368, after `setSessionCost` in the cost handler

```javascript
// --- FIND (lines 359-369): ---
            } else if (event.type === 'cost') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, cost: event }
                }
                return updated
              })
              setSessionCost(prev => prev + (event.total_cost || 0))
            } else if (event.type === 'error') {

// --- REPLACE WITH: ---
            } else if (event.type === 'cost') {
              setMessages(prev => {
                const updated = [...prev]
                const last = updated[updated.length - 1]
                if (last && last.role === 'assistant') {
                  updated[updated.length - 1] = { ...last, cost: event }
                }
                return updated
              })
              setSessionCost(prev => prev + (event.total_cost || 0))
              if (event.high_cost && addToast) {
                addToast('Expensive query: $' + event.total_cost.toFixed(4) + '. Try a more specific question to reduce cost.', 'warning', 8000)
              }
            } else if (event.type === 'error') {
```

### Edit 2C: Color-code per-message cost (lines 834-844)

**Location:** Lines 834-844, the per-message cost display

```javascript
// --- FIND (lines 834-844): ---
              {msg.cost && msg.cost.total_cost > 0 && (
                <div style={{
                  marginTop: '6px',
                  fontSize: '0.7rem',
                  color: 'var(--text-secondary)',
                  opacity: 0.6,
                }}>
                  ${msg.cost.total_cost.toFixed(4)}
                  {msg.cost.tts_cost > 0 ? ' (incl. voice)' : ''}
                </div>
              )}

// --- REPLACE WITH: ---
              {msg.cost && msg.cost.total_cost > 0 && (
                <div style={{
                  marginTop: '6px',
                  fontSize: '0.7rem',
                  color: msg.cost.total_cost > 0.25 ? '#f87171' :
                         msg.cost.total_cost > 0.05 ? '#fbbf24' :
                         'var(--text-secondary)',
                  opacity: msg.cost.total_cost > 0.05 ? 0.9 : 0.6,
                  fontWeight: msg.cost.total_cost > 0.25 ? 600 : 400,
                }}>
                  ${msg.cost.total_cost.toFixed(4)}
                  {msg.cost.tts_cost > 0 ? ' (incl. voice)' : ''}
                  {msg.cost.total_cost > 0.25 ? ' — high cost' : ''}
                </div>
              )}
```

---

## What Each Guardrail Does

| Guardrail | Trigger | Effect |
|-----------|---------|--------|
| **Tool response truncation** | Any tool returns >8,000 chars | Cuts to 8K + note. AI gets enough data, doesn't waste tokens on the rest. |
| **Max rounds reduced** | Always | 3 rounds instead of 5. Most queries finish in 1-2. |
| **Per-round cost check** | After round 1, cost >$0.25 | Stops the tool loop, fires `cost_warning` SSE event. |
| **High cost flag** | Final query cost >$0.25 | Adds `high_cost: true` to cost event → toast in UI. |
| **Cost color coding** | Always shown | Green <$0.05, yellow $0.05-$0.25, red >$0.25. |
| **Warning toast** | Query cost >$0.25 | "Expensive query" toast persists 8 seconds with suggestion. |

## Verification
1. `python -c "import ast; ast.parse(open('backend/routes/assistant_routes.py').read())"` passes
2. `cd frontend && npm run build` succeeds
3. Cheap query (e.g., "how did Period 2 do?") → no warnings, cost in default gray
4. Trigger an expensive query → yellow/red cost label, warning toast fires
5. A tool returning >8K chars gets truncated (visible in tool_result preview)
6. Tool loop stops after 3 rounds max
7. Session cost in header still accumulates correctly
