from __future__ import annotations

from services.market_data import fetch_bitcoin, fetch_eurusd, fetch_yf


# ── Instrument registry ──────────────────────────────────────────────────────────

INSTRUMENTS: list[dict] = [
    {
        "key":       "bitcoin",
        "label":     "Bitcoin",
        "fetch":     fetch_bitcoin,
        "prefix":    "$",
        "suffix":    "",
        "decimals":  2,
        "thousands": True,
        "ticker":    "BTC-USD",
        "icon":      "&#x20BF;",
        "accent":    "#f7931a",
    },
    {
        "key":       "gold",
        "label":     "Gold",
        "fetch":     lambda: fetch_yf("GC=F"),
        "prefix":    "$",
        "suffix":    " /oz",
        "decimals":  2,
        "thousands": True,
        "ticker":    "GC=F",
        "icon":      "&#9670;",
        "accent":    "#f59e0b",
    },
    {
        "key":       "silver",
        "label":     "Silver",
        "fetch":     lambda: fetch_yf("SI=F"),
        "prefix":    "$",
        "suffix":    " /oz",
        "decimals":  3,
        "thousands": False,
        "ticker":    "SI=F",
        "icon":      "&#9671;",
        "accent":    "#94a3b8",
    },
    {
        "key":       "copper",
        "label":     "Copper",
        "fetch":     lambda: fetch_yf("HG=F"),
        "prefix":    "$",
        "suffix":    " /lb",
        "decimals":  4,
        "thousands": False,
        "ticker":    "HG=F",
        "icon":      "&#9679;",
        "accent":    "#c87941",
    },
    {
        "key":       "eurusd",
        "label":     "EUR / USD",
        "fetch":     fetch_eurusd,
        "prefix":    "",
        "suffix":    "",
        "decimals":  4,
        "thousands": False,
        "ticker":    "EURUSD=X",
        "icon":      "&#8364;/$",
        "accent":    "#3b82f6",
    },
    {
        "key":       "brent",
        "label":     "Brent Crude",
        "fetch":     lambda: fetch_yf("BZ=F"),
        "prefix":    "$",
        "suffix":    " /bbl",
        "decimals":  2,
        "thousands": False,
        "ticker":    "BZ=F",
        "icon":      "&#9679;",
        "accent":    "#10b981",
    },
    {
        "key":       "henryhub",
        "label":     "Henry Hub Gas",
        "fetch":     lambda: fetch_yf("NG=F"),
        "prefix":    "$",
        "suffix":    " /MMBtu",
        "decimals":  3,
        "thousands": False,
        "ticker":    "NG=F",
        "icon":      "&#128293;",
        "accent":    "#8b5cf6",
    },
    {
        "key":       "ttfgas",
        "label":     "TTF Gas",
        "fetch":     lambda: fetch_yf("TTF=F"),
        "prefix":    "\u20ac",
        "suffix":    " /MWh",
        "decimals":  2,
        "thousands": False,
        "ticker":    "TTF=F",
        "icon":      "&#9889;",
        "accent":    "#f43f5e",
    },
]

INSTRUMENT_MAP = {i["key"]: i for i in INSTRUMENTS}


# ── Static summaries (overview + outlook stay static; bullets used as fallback) ──

SUMMARIES: dict[str, dict] = {
    "bitcoin": {
        "overview": (
            "Bitcoin is the world's leading digital asset, with a fixed supply cap of 21 million coins. "
            "Its price is driven by institutional adoption cycles, macroeconomic liquidity, and the "
            "four-year halving schedule that periodically cuts new supply issuance in half."
        ),
        "macro": [
            "Spot Bitcoin ETF approvals (Jan 2024) unlocked institutional capital at scale",
            "Fed rate cuts in 2024-25 boosted risk appetite across digital assets",
            "April 2024 halving reduced block reward to 3.125 BTC — historical bull catalyst",
            "US national debt concerns driving 'digital gold' store-of-value narrative",
            "Corporate treasury adoption (MicroStrategy, Tesla) creates structural demand floor",
        ],
        "geopolitical": [
            "Pro-crypto regulatory shift under 2024-25 US administration eased compliance barriers",
            "El Salvador and other nations adopting BTC as legal tender signals sovereign demand",
            "China's mining ban pushed hashrate to US, Canada, and Kazakhstan",
            "Russia and Iran reported use of crypto to circumvent Western financial sanctions",
            "US Bitcoin Strategic Reserve proposal added a new sovereign demand narrative",
        ],
        "outlook": (
            "Bitcoin's medium-term trajectory is tied to global liquidity expansion, ETF inflow momentum, "
            "and the diminishing post-halving supply. Regulatory clarity in the US and Europe remains the "
            "key variable for the next wave of institutional adoption."
        ),
    },
    "gold": {
        "overview": (
            "Gold is the world's premier safe-haven asset and inflation hedge, with a 5,000-year track record "
            "as a store of value. Record central bank purchases since 2022, combined with geopolitical "
            "fragmentation and US fiscal concerns, have supported prices above $2,000/oz structurally."
        ),
        "macro": [
            "Fed rate pivot (2024-25) and dollar weakness are the primary bullish catalysts",
            "US national debt exceeding $35 trillion eroding confidence in USD as reserve asset",
            "Declining real yields increase the relative attractiveness of non-yielding gold",
            "Persistent services inflation sustaining the hedge and safe-haven narrative",
            "Gold ETF inflows and managed money long positioning at multi-year highs",
        ],
        "geopolitical": [
            "Central bank buying at record pace: China, India, Poland, Turkey all major buyers",
            "BRICS nations actively diversifying reserves away from US Treasuries into gold",
            "Russia-Ukraine war and Middle East conflict driving safe-haven premium",
            "Western sanctions on Russia (2022) demonstrated dollar weaponisation risk to EM holders",
            "De-dollarisation trend accelerating non-Western central bank accumulation",
        ],
        "outlook": (
            "Gold's structural bull case rests on central bank reserve diversification, declining real rates, "
            "and persistent geopolitical uncertainty. The key near-term variables are the pace of Fed easing "
            "and whether EM central banks maintain their record purchasing cadence."
        ),
    },
    "silver": {
        "overview": (
            "Silver uniquely straddles the precious metals and industrial commodities markets. "
            "Nearly 60% of demand now comes from industrial applications — with solar photovoltaics, "
            "electric vehicles, and advanced electronics representing the fastest-growing segments "
            "— while investment demand adds a macro overlay."
        ),
        "macro": [
            "Solar panel manufacturing is the fastest-growing silver demand segment globally",
            "Each GW of solar capacity requires ~70 tonnes of silver — IRA and EU Green Deal driving build-out",
            "Gold/silver ratio above 80 historically signals silver is undervalued relative to gold",
            "Physical silver market ran a structural deficit for three consecutive years (2021-23)",
            "Rising industrial demand increasingly offsetting weaker jewellery and coin investment",
        ],
        "geopolitical": [
            "~75% of silver mined as a byproduct of lead, zinc, and copper — supply tied to base metals cycle",
            "Mexico and Peru supply ~40% of global silver — political instability (Peru strikes) a risk",
            "US-China trade tensions affecting solar panel supply chains and silver demand forecasts",
            "Green energy subsidies (US IRA, EU taxonomy) structurally accelerating solar silver demand",
            "Tight LBMA and COMEX warehouse inventories amplify short-term supply squeezes",
        ],
        "outlook": (
            "Silver's dual precious/industrial role makes it a beneficiary of both risk-on (industrial demand) "
            "and risk-off (safe-haven) environments. The energy transition megatrend provides a long-term "
            "structural demand tailwind, while near-term price action continues to shadow gold's moves."
        ),
    },
    "copper": {
        "overview": (
            "Copper, the essential metal of electrification, is critical infrastructure for EVs, "
            "renewable energy, and power grid upgrades. Growing long-term demand against a supply "
            "pipeline constrained by permitting delays, aging mines, and political risk is creating "
            "a structural deficit outlook for the next decade."
        ),
        "macro": [
            "China consumes ~55% of global copper — PMI readings are the key near-term price signal",
            "Each EV requires 4x more copper than an internal-combustion vehicle",
            "Offshore wind turbines require 8-10 tonnes of copper per MW of installed capacity",
            "US and EU grid modernisation programmes require billions of metres of new copper cable",
            "Mine supply growth constrained: average 15-20 year permitting timeline for new projects",
        ],
        "geopolitical": [
            "Chile and Peru supply ~40% of global copper — labour strikes and left-wing policy risk",
            "DRC's Kamoa-Kakula mine is a major new swing producer but faces logistics constraints",
            "US tariffs on Chinese manufactured goods affecting downstream copper product demand",
            "China stimulus packages (property sector, infrastructure) directly drive price spikes",
            "Water scarcity in Chile's Atacama Desert threatens output at major mines long-term",
        ],
        "outlook": (
            "Copper's long-term bull case — driven by global electrification — is structurally sound. "
            "Near-term prices remain hostage to Chinese economic data, but the decade-long supply "
            "deficit thesis is increasingly consensus among major mining houses and investment banks."
        ),
    },
    "eurusd": {
        "overview": (
            "EUR/USD is the world's most traded currency pair, accounting for ~23% of daily FX volume. "
            "It reflects the monetary policy and economic divergence between the Eurozone and the "
            "United States, and serves as a key barometer of global risk appetite and dollar strength."
        ),
        "macro": [
            "ECB vs Fed rate differential: narrowing as both institutions cut through 2024-25",
            "Eurozone manufacturing in prolonged recession, weighing on euro growth fundamentals",
            "US economic exceptionalism — stronger growth and productivity — maintaining dollar demand",
            "ECB quantitative tightening (balance sheet reduction) providing a longer-term euro floor",
            "Euro area services sector showing resilience; PMI divergence vs. industry remains wide",
        ],
        "geopolitical": [
            "Russia-Ukraine war energy impact structurally raised European production costs vs. US",
            "US tariff threats on European auto and industrial exports (2025 trade policy escalation)",
            "French fiscal trajectory and debt-to-GDP ratio weighing on euro area credibility",
            "German industrial competitiveness declining — energy cost disadvantage vs. US and Asia",
            "USD retains global reserve currency status, providing a structural demand floor",
        ],
        "outlook": (
            "EUR/USD near-term direction hinges on the relative pace of Fed versus ECB rate cuts and "
            "whether European growth can recover from its manufacturing slump. US tariff escalation "
            "represents the key downside risk to the euro; any positive Ukraine resolution could "
            "trigger a sharp relief rally."
        ),
    },
    "brent": {
        "overview": (
            "Brent Crude is the global benchmark for oil pricing, covering ~60% of international trade. "
            "Supply decisions from OPEC+, record US shale output, and demand growth from China and India "
            "are the dominant price drivers, while energy transition narratives weigh on the long-term outlook."
        ),
        "macro": [
            "OPEC+ voluntary production cuts supporting price floor, but compliance varies by member",
            "US shale output at record highs (~13 mb/d) is effectively capping prices above $90/bbl",
            "China demand recovery uneven — aviation and transport strong, industrial segment soft",
            "India emerging as the primary demand growth engine, partially replacing slowing China",
            "IEA projects peak oil demand in advanced economies before 2030 — long-term headwind",
        ],
        "geopolitical": [
            "Russia's oil redirected to India and China after G7 price cap and Western sanctions",
            "Middle East conflict (Israel-Gaza, Iran tensions) embeds a risk premium in Brent",
            "Houthi Red Sea attacks forcing shipping route diversions and raising freight costs",
            "Iran sanctions enforcement (variable) affecting ~1-1.5 million bpd of supply",
            "Libya and Nigeria chronic production disruptions add persistent supply-side volatility",
        ],
        "outlook": (
            "Brent is caught between OPEC+ supply discipline providing a floor and rising non-OPEC "
            "production limiting the ceiling. Middle East escalation risk remains the key upside catalyst, "
            "while a deeper-than-expected Chinese slowdown is the primary downside risk."
        ),
    },
    "henryhub": {
        "overview": (
            "Henry Hub is the primary US natural gas pricing benchmark, located in Erath, Louisiana. "
            "Prices reflect the balance between prolific US shale gas production, growing LNG export "
            "volumes, domestic power generation demand, and highly weather-sensitive consumption patterns."
        ),
        "macro": [
            "US dry gas production at record highs (~105 Bcf/day) — Haynesville and Permian leading",
            "LNG export capacity expansion creates a growing arbitrage link to international prices",
            "Power sector gas demand growing as coal retires and gas backs up intermittent renewables",
            "Storage levels vs. the 5-year seasonal average is the key near-term price indicator",
            "Permian Basin associated gas production grows automatically alongside oil output",
        ],
        "geopolitical": [
            "European LNG demand surge post-2022 linked US and EU gas markets structurally",
            "New LNG export terminals (Plaquemines, Golden Pass) increasing export optionality",
            "Mexico pipeline exports expanding, tying US supply to Latin American demand",
            "FERC permitting uncertainty for next-wave LNG projects creating investment caution",
            "Asian LNG demand (Japan, South Korea, China) competing with Europe for US cargoes",
        ],
        "outlook": (
            "Henry Hub prices remain structurally suppressed by abundant US shale supply, but growing "
            "LNG export capacity is gradually tightening the domestic market. Cold winter weather and "
            "LNG terminal outages remain the primary short-term volatility catalysts."
        ),
    },
    "ttfgas": {
        "overview": (
            "TTF (Title Transfer Facility) is Europe's primary natural gas trading hub, based in the "
            "Netherlands. European gas prices are driven by the near-complete loss of Russian pipeline "
            "supply, reliance on LNG imports, seasonal storage dynamics, and renewable intermittency."
        ),
        "macro": [
            "European LNG import infrastructure massively expanded post-2022 crisis (FSRU terminals)",
            "EU storage typically targets 90%+ fill by November — summer/autumn injection season is key",
            "EU ETS carbon pricing (~EUR 60-80/tonne) adds a structural cost floor for gas consumers",
            "Renewable intermittency (wind droughts, low solar in winter) spikes gas demand as backup",
            "Industrial demand destruction during 2022-23 price spike structurally reduced European consumption",
        ],
        "geopolitical": [
            "Russian pipeline gas flows (Nord Stream destroyed, TurkStream reduced) largely eliminated",
            "Norway is now Europe's single largest gas supplier — pipeline integrity is critical",
            "Algeria and Azerbaijan pipeline volumes partially, but not fully, replacing Russian supply",
            "LNG cargo competition: Europe bids against Japan, South Korea, China for spot cargoes",
            "Ukraine transit agreement expiry affecting remaining Russian transit through Eastern Europe",
        ],
        "outlook": (
            "European TTF prices have normalised significantly from the 2022 crisis peaks but remain "
            "structurally above pre-2021 levels. Key risk factors are a cold winter drawing down storage "
            "rapidly, any Norwegian pipeline outage, or LNG supply disruptions — all of which could "
            "trigger sharp price spikes given Europe's reduced buffer capacity."
        ),
    },
}


# ── Context search queries for Google News RSS (macro + geopolitical) ────────────

CONTEXT_QUERIES = {
    "bitcoin":  "bitcoin price market ETF regulation economic",
    "gold":     "gold price market central bank inflation economic",
    "silver":   "silver price market industrial demand supply",
    "copper":   "copper price market China demand supply",
    "eurusd":   "EUR USD euro dollar exchange rate ECB Fed",
    "brent":    "brent crude oil price OPEC energy supply",
    "henryhub": "natural gas price LNG market Henry Hub",
    "ttfgas":   "European TTF gas price energy market supply",
}
