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
- Use subagents for parallelizable work.
- Do not proceed to a later phase until the current phase is actually working.
