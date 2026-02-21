# Phase 7: Cloud Run Deployment - Context

**Gathered:** 2026-02-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Deploy the Knowledge Hub pipeline to Google Cloud Run with proper secrets management, structured logging, operational configuration, weekly digest, and cost tracking. The pipeline already works locally — this phase makes it production-ready.

</domain>

<decisions>
## Implementation Decisions

### GCP setup
- Use existing GCP project (user already has one)
- Deploy to **europe-west4** (Netherlands)
- Manual deployment via `gcloud run deploy` — no CI/CD pipeline
- Use default Cloud Run `*.run.app` URL — no custom domain

### Cost tracking
- Log Gemini token usage and cost per entry in structured JSON logs (full detail: tokens, model, cost)
- Include **total cost only** (e.g., "Cost: $0.003") in Slack confirmation replies — no token breakdown
- Include weekly total Gemini cost in the weekly digest
- **Daily cost alert**: Send Slack DM if daily Gemini spend exceeds **$5/day**

### Weekly digest
- Send **Monday morning** (summarizing previous week's entries)
- Deliver as a **DM** to the user — not in #knowledge-base channel
- Content includes all of:
  - Entry count + list of titles with Notion links
  - Category breakdown (e.g., 3 articles, 2 videos)
  - Top tags that week
  - Total Gemini cost for the week
- **Always send**, even if zero entries — confirms the service is running ("No entries this week")

### Claude's Discretion
- Docker base image and build configuration
- Secret Manager integration pattern
- Structured log field schema (beyond cost fields)
- Cloud Run instance sizing (memory, CPU)
- Slack signature verification implementation
- Cold start mitigation approach (min-instances=1 is required, details flexible)
- Scheduling mechanism for weekly digest (Cloud Scheduler, cron, etc.)
- Cost alert tracking mechanism (how to accumulate daily costs)

</decisions>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 07-cloud-run-deployment*
*Context gathered: 2026-02-21*
