# MarketScope — Claude Development Rules

## External dependencies
- For any external API, data provider, charting library, article source, or parser, check the latest official documentation before implementing.
- Prefer official docs over memory.
- If the source cannot support the feature, do not pretend it can.

## UI discipline
- Do not leave placeholder UI that is not wired.
- Do not add unexplained UI indicators.
- Accuracy is more important than density or visual complexity.

## Data integrity
- Keep spot, front future, and curve data clearly separated.
- If a source cannot provide the required data, say so explicitly and make the adapter replaceable.

## Agent workflow
- Default to using subagents for any task involving multiple systems or files.
- Do not proceed to a later phase until the current phase is actually working.

## Subagent workflow (mandatory)

Claude must decompose non-trivial tasks into subagents whenever possible.

Use subagents for parallelizable workstreams such as:
- market data ingestion
- futures contract chains
- FX and crypto feeds
- chart rendering
- UI debugging
- API infrastructure
- news ingestion and ranking

Rules:
- Default behaviour should be to create subagents.
- Single-agent execution should only occur for trivial edits.
- Independent tasks should run in parallel.
- Each subagent must focus on one domain.
- The orchestrator agent merges results after completion.

### Standard MarketScope agent roles

**market-data-agent**
Responsible for:
- price providers
- futures contract chains
- spot benchmarks
- FX feeds
- crypto feeds

**charts-agent**
Responsible for:
- price charts
- forward curves
- spreads
- modal chart rendering

**infra-agent**
Responsible for:
- API endpoints
- caching
- logging
- debug tools
- provider adapters

**news-agent**
Responsible for:
- article ingestion
- deduplication
- relevance scoring
- summaries
- paywall handling

### Execution rule

If a task touches multiple subsystems, Claude should automatically spawn the relevant subagents and run them in parallel before merging results.
