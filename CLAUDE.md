# MarketScope — Claude Development Rules

## External dependencies
- For any external API, library, market-data source, charting library, article source, or parsing dependency, check the latest official documentation before implementing.
- Prefer official documentation over memory.
- If documentation is unclear, do not guess.

## UI discipline
- Do not add unexplained UI indicators.
- Do not leave placeholder UI for data features that are not wired.
- Accuracy is more important than visual complexity.

## Data integrity
- Keep spot, futures, and curve data clearly separated.
- If a source cannot provide the required data, say so explicitly and make the adapter replaceable.

## Agent workflow
- Use subagents for parallelizable workstreams.
- Do not proceed to a later phase until the current phase is actually working.
