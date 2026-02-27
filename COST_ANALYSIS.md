# AI Cost Analysis — AgentForge Healthcare

## 1. Development Costs

| Category | Estimate |
|----------|----------|
| Agent development & testing | ~200 API calls |
| Eval suite runs (57 cases x 3 runs) | ~171 API calls |
| Debugging & iteration | ~100 API calls |
| **Total development calls** | **~470 calls** |
| **Estimated dev cost** | **~$3.50** |

Development used Claude Sonnet 4 at $3/M input tokens, $15/M output tokens.

## 2. Per-Query Cost Breakdown

Based on 57 eval runs with real OpenEMR data:

| Metric | Value |
|--------|-------|
| Avg input tokens/query | ~2,500 (system prompt + tools + user message + FHIR data) |
| Avg output tokens/query | ~270 (based on avg 1,083 char response) |
| Avg tool calls/query | 1.1 |
| Avg latency | 12.8s |

### Cost Per Query (Claude Sonnet 4)

| Component | Tokens | Rate | Cost |
|-----------|--------|------|------|
| Input | 2,500 | $3.00/M | $0.0075 |
| Output | 270 | $15.00/M | $0.0041 |
| **Total per query** | | | **$0.0116** |

~1.2 cents per query.

## 3. Production Cost Projections

Assumptions:
- 3 queries per user per day
- 30 days per month
- 90 queries/user/month
- Claude Sonnet 4 pricing ($3/$15 per M tokens)

| Scale | Users | Queries/mo | Monthly Cost | Cost/User/mo |
|-------|-------|-----------|-------------|-------------|
| Small clinic | 10 | 900 | $10.44 | $1.04 |
| Practice group | 100 | 9,000 | $104 | $1.04 |
| Regional health system | 1,000 | 90,000 | $1,044 | $1.04 |
| Large hospital network | 10,000 | 900,000 | $10,440 | $1.04 |
| Enterprise | 100,000 | 9,000,000 | $104,400 | $1.04 |

## 4. Cost Optimization Strategies

### Response Caching (Est. 40-60% cost reduction)
- Cache common queries (drug interactions, symptom lookups) with TTL
- Same patient summary within 5 minutes returns cached result
- Projected savings at 1,000 users: $1,044 → ~$520/mo

### Model Tiering (Est. 30-50% cost reduction)
- Route simple queries (greetings, FAQ) to Claude Haiku ($0.25/$1.25 per M tokens)
- Reserve Sonnet for complex clinical reasoning (multi-step, drug interactions)
- Estimated 60% of queries are simple → blended cost ~$0.006/query

### Prompt Optimization (Est. 10-20% cost reduction)
- Compress system prompt and tool descriptions
- Use structured output schemas to reduce output tokens
- Batch FHIR API calls to reduce round-trips (lower latency, fewer retries)

### Combined Optimization Projections

| Scale | Users | Unoptimized | Optimized (est.) | Savings |
|-------|-------|------------|-------------------|---------|
| Small clinic | 10 | $10/mo | $4/mo | 60% |
| Practice group | 100 | $104/mo | $42/mo | 60% |
| Regional | 1,000 | $1,044/mo | $418/mo | 60% |
| Enterprise | 100,000 | $104,400/mo | $41,760/mo | 60% |

## 5. Cost Comparison

| Solution | Monthly Cost (100 users) | Per-user/mo |
|----------|------------------------|-------------|
| **AgentForge (unoptimized)** | **$104** | **$1.04** |
| **AgentForge (optimized)** | **~$42** | **~$0.42** |
| UpToDate subscription | $5,000+ | $50+ |
| Lexicomp/Clinical Pharmacology | $3,000+ | $30+ |
| Epic CDS module | $50,000+ | $500+ |

AgentForge delivers clinical decision support at **1-2% of the cost** of enterprise alternatives while using real-time patient data from the EHR.

## 6. Key Assumptions & Limitations

- Token estimates based on 57 real eval runs against OpenEMR FHIR API
- Actual production usage patterns may differ (more complex queries, longer conversations)
- Pricing based on Anthropic Claude Sonnet 4 as of Feb 2026
- Does not include infrastructure costs (Railway: ~$5/mo, OpenEMR hosting: variable)
- Multi-turn conversations will increase input tokens due to conversation history
