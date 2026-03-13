from __future__ import annotations

from services.market_data import fetch_bitcoin, fetch_ethereum, fetch_eurusd, fetch_yf


# ── Instrument registry ──────────────────────────────────────────────────────────

INSTRUMENTS: list[dict] = [
    # ── Crypto ──────────────────────────────────────────────────────────────────
    # Real-time spot prices from Binance; yfinance used for history only.
    {
        "key":            "bitcoin",
        "label":          "Bitcoin",
        "fetch":          fetch_bitcoin,
        "provider":       "binance",
        "prefix":         "$",
        "suffix":         "",
        "decimals":       2,
        "thousands":      True,
        "ticker":         "BTC-USD",
        "icon":           "&#x20BF;",
        "accent":         "#f7931a",
        "asset_class":    "crypto",
        "price_type":     "spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "ethereum",
        "label":          "Ethereum",
        "fetch":          fetch_ethereum,
        "provider":       "binance",
        "prefix":         "$",
        "suffix":         "",
        "decimals":       2,
        "thousands":      True,
        "ticker":         "ETH-USD",
        "icon":           "&#926;",
        "accent":         "#627eea",
        "asset_class":    "crypto",
        "price_type":     "spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    # ── Metals — COMEX/NYMEX futures only; no free reliable spot source ─────────
    {
        "key":            "gold",
        "label":          "Gold",
        "fetch":          lambda: fetch_yf("GC=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /oz",
        "decimals":       2,
        "thousands":      True,
        "ticker":         "GC=F",
        "icon":           "&#9670;",
        "accent":         "#f59e0b",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,   # LBMA spot requires paid data
        "contract_label": "COMEX Front (GC=F)",
        "curve_enabled":  True,
        "curve_root":     "GC",
        "curve_months":   ["G", "J", "M", "Q", "V", "Z"],  # bi-monthly active
        "curve_n":        8,
    },
    {
        "key":            "silver",
        "label":          "Silver",
        "fetch":          lambda: fetch_yf("SI=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /oz",
        "decimals":       3,
        "thousands":      False,
        "ticker":         "SI=F",
        "icon":           "&#9671;",
        "accent":         "#94a3b8",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "COMEX Front (SI=F)",
        "curve_enabled":  True,
        "curve_root":     "SI",
        "curve_months":   ["H", "K", "N", "U", "Z"],
        "curve_n":        6,
    },
    {
        "key":            "copper",
        "label":          "Copper",
        "fetch":          lambda: fetch_yf("HG=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /lb",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "HG=F",
        "icon":           "&#9679;",
        "accent":         "#c87941",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "COMEX Front (HG=F)",
        "curve_enabled":  True,
        "curve_root":     "HG",
        "curve_months":   ["H", "K", "N", "U", "Z"],
        "curve_n":        6,
    },
    {
        "key":            "platinum",
        "label":          "Platinum",
        "fetch":          lambda: fetch_yf("PL=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /oz",
        "decimals":       2,
        "thousands":      False,
        "ticker":         "PL=F",
        "icon":           "&#9671;",
        "accent":         "#cbd5e1",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (PL=F)",
        "curve_enabled":  True,
        "curve_root":     "PL",
        "curve_months":   ["F", "J", "N", "V"],  # quarterly
        "curve_n":        5,
    },
    # ── FX — interbank spot rates (not futures) ─────────────────────────────────
    {
        "key":            "eurusd",
        "label":          "EUR / USD",
        "fetch":          fetch_eurusd,
        "provider":       "frankfurter",
        "prefix":         "",
        "suffix":         "",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "EURUSD=X",
        "icon":           "&#8364;/$",
        "accent":         "#3b82f6",
        "asset_class":    "fx",
        "price_type":     "fx_spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "gbpusd",
        "label":          "GBP / USD",
        "fetch":          lambda: fetch_yf("GBPUSD=X"),
        "provider":       "yfinance",
        "prefix":         "",
        "suffix":         "",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "GBPUSD=X",
        "icon":           "&#163;/$",
        "accent":         "#e11d48",
        "asset_class":    "fx",
        "price_type":     "fx_spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "usdjpy",
        "label":          "USD / JPY",
        "fetch":          lambda: fetch_yf("JPY=X"),
        "provider":       "yfinance",
        "prefix":         "",
        "suffix":         "",
        "decimals":       2,
        "thousands":      False,
        "ticker":         "JPY=X",
        "icon":           "&#165;",
        "accent":         "#ef4444",
        "asset_class":    "fx",
        "price_type":     "fx_spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "usdcnh",
        "label":          "USD / CNH",
        "fetch":          lambda: fetch_yf("CNH=X"),
        "provider":       "yfinance",
        "prefix":         "",
        "suffix":         "",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "CNH=X",
        "icon":           "&#20803;",
        "accent":         "#f59e0b",
        "asset_class":    "fx",
        "price_type":     "fx_spot",
        "spot_available": True,
        "contract_label": None,
        "curve_enabled":  False,
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    # ── Energy — NYMEX/ICE futures only; physical spot is OTC / paid ────────────
    {
        "key":            "brent",
        "label":          "Brent Crude",
        "fetch":          lambda: fetch_yf("BZ=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /bbl",
        "decimals":       2,
        "thousands":      False,
        "ticker":         "BZ=F",
        "icon":           "&#9679;",
        "accent":         "#10b981",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,   # Dated Brent is Platts/OPIS — paid
        "contract_label": "ICE Front (BZ=F)",
        "curve_enabled":  True,
        "curve_root":     "BZ",
        "curve_months":   ["F","G","H","J","K","M","N","Q","U","V","X","Z"],
        "curve_n":        8,
    },
    {
        "key":            "wti",
        "label":          "WTI Crude",
        "fetch":          lambda: fetch_yf("CL=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /bbl",
        "decimals":       2,
        "thousands":      False,
        "ticker":         "CL=F",
        "icon":           "&#9679;",
        "accent":         "#ef4444",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (CL=F)",
        "curve_enabled":  True,
        "curve_root":     "CL",
        "curve_months":   ["F","G","H","J","K","M","N","Q","U","V","X","Z"],
        "curve_n":        8,
    },
    {
        "key":            "henryhub",
        "label":          "Henry Hub Gas",
        "fetch":          lambda: fetch_yf("NG=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /MMBtu",
        "decimals":       3,
        "thousands":      False,
        "ticker":         "NG=F",
        "icon":           "&#128293;",
        "accent":         "#8b5cf6",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (NG=F)",
        "curve_enabled":  True,
        "curve_root":     "NG",
        "curve_months":   ["F","G","H","J","K","M","N","Q","U","V","X","Z"],
        "curve_n":        8,
    },
    {
        "key":            "ttfgas",
        "label":          "TTF Gas",
        "fetch":          lambda: fetch_yf("TTF=F"),
        "provider":       "yfinance",
        "prefix":         "\u20ac",
        "suffix":         " /MWh",
        "decimals":       2,
        "thousands":      False,
        "ticker":         "TTF=F",
        "icon":           "&#9889;",
        "accent":         "#f43f5e",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "ICE Front (TTF=F)",
        "curve_enabled":  False,   # ICE TTF individual months unreliable in yfinance
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "rbobgas",
        "label":          "RBOB Gasoline",
        "fetch":          lambda: fetch_yf("RB=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /gal",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "RB=F",
        "icon":           "&#9679;",
        "accent":         "#16a34a",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (RB=F)",
        "curve_enabled":  True,
        "curve_root":     "RB",
        "curve_months":   ["F","G","H","J","K","M","N","Q","U","V","X","Z"],
        "curve_n":        6,
    },
    {
        "key":            "heatingoil",
        "label":          "Heating Oil",
        "fetch":          lambda: fetch_yf("HO=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /gal",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "HO=F",
        "icon":           "&#9679;",
        "accent":         "#0ea5e9",
        "asset_class":    "energy",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (HO=F)",
        "curve_enabled":  True,
        "curve_root":     "HO",
        "curve_months":   ["F","G","H","J","K","M","N","Q","U","V","X","Z"],
        "curve_n":        6,
    },
    {
        "key":            "aluminium",
        "label":          "Aluminium",
        "fetch":          lambda: fetch_yf("ALI=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /lb",
        "decimals":       4,
        "thousands":      False,
        "ticker":         "ALI=F",
        "icon":           "&#9671;",
        "accent":         "#64748b",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "CME Front (ALI=F)",
        "curve_enabled":  False,   # CME ALI individual contract coverage in yfinance is incomplete
        "curve_root":     None,
        "curve_months":   [],
        "curve_n":        0,
    },
    {
        "key":            "palladium",
        "label":          "Palladium",
        "fetch":          lambda: fetch_yf("PA=F"),
        "provider":       "yfinance",
        "prefix":         "$",
        "suffix":         " /oz",
        "decimals":       2,
        "thousands":      True,
        "ticker":         "PA=F",
        "icon":           "&#9671;",
        "accent":         "#7c3aed",
        "asset_class":    "metal",
        "price_type":     "futures",
        "spot_available": False,
        "contract_label": "NYMEX Front (PA=F)",
        "curve_enabled":  True,
        "curve_root":     "PA",
        "curve_months":   ["H", "M", "U", "Z"],
        "curve_n":        5,
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
    "ethereum": {
        "overview": (
            "Ethereum is the world's leading programmable blockchain, underpinning the majority of "
            "decentralised finance (DeFi), NFT infrastructure, and Web3 applications. Its transition "
            "to Proof-of-Stake ('The Merge', 2022) made ETH a yield-bearing, deflationary asset "
            "with a supply issuance directly tied to network usage."
        ),
        "macro": [
            "Spot Ethereum ETF approvals (mid-2024) opened institutional capital flows into ETH",
            "EIP-1559 fee burn mechanism makes ETH deflationary when network demand is high",
            "Layer-2 scaling (Arbitrum, Optimism, Base) reducing fees and driving DeFi adoption",
            "ETH staking yield (~4-5% APR) positions it as a 'crypto bond' vs. Bitcoin's 'digital gold'",
            "Risk appetite and liquidity cycles closely mirror Bitcoin — Fed policy the dominant macro signal",
        ],
        "geopolitical": [
            "US SEC ETF approvals marked a regulatory turning point for Ethereum institutional adoption",
            "EU MiCA regulation providing clearer compliance framework for ETH-based DeFi products",
            "China's DeFi and crypto trading restrictions limit but do not eliminate mainland exposure",
            "Ethereum Foundation's global developer base provides censorship-resistance vs. national restrictions",
            "Sanctions compliance in DeFi remains a key regulatory flashpoint for ETH infrastructure",
        ],
        "outlook": (
            "Ethereum's medium-term outlook depends on Layer-2 ecosystem growth sustaining on-chain fee "
            "revenue and the continued expansion of real-world asset tokenisation on the base layer. "
            "Spot ETF inflows and staking adoption are the primary catalysts for the next re-rating cycle."
        ),
    },
    "platinum": {
        "overview": (
            "Platinum is a rare precious metal with critical industrial applications in automotive catalysts, "
            "hydrogen fuel cells, and chemical manufacturing. Supply is highly concentrated — over 70% comes "
            "from South Africa — while demand is split between autocatalysis (petrol engines), jewellery, "
            "and the emerging green hydrogen economy."
        ),
        "macro": [
            "Platinum trades at a significant discount to palladium, reversing its historic premium",
            "Hydrogen fuel cell technology (PEM electrolysers) is the primary long-term demand growth driver",
            "ICE vehicle production — the main demand source — gradually declining as EV share rises",
            "Gold/platinum ratio above 1.0x historically signals platinum undervaluation vs. gold",
            "Industrial demand from chemicals, glass, and refinery sectors provides a stable demand base",
        ],
        "geopolitical": [
            "South Africa supplies ~75% of global platinum — power outages (load-shedding) and labour strikes are key supply risks",
            "Russian sanctions (Norilsk Nickel) affected palladium more than platinum, but highlighted supply concentration risk",
            "Green hydrogen investment programmes (EU Hydrogen Strategy, US IRA) boosting PEM electrolyser demand",
            "Zimbabwe's platinum output growing, partially diversifying supply from South Africa",
            "EU and US emission standards affecting autocatalyst demand: diesel catalyst phase-out is a structural headwind",
        ],
        "outlook": (
            "Platinum's near-term price faces headwinds from the EV transition reducing autocatalyst demand, "
            "but the hydrogen economy megatrend offers a long-term structural demand tailwind. South African "
            "supply constraints and the historically wide gold/platinum spread provide a valuation floor argument."
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
    "gbpusd": {
        "overview": (
            "GBP/USD ('Cable') is one of the oldest and most liquid currency pairs, reflecting the economic "
            "and monetary policy divergence between the United Kingdom and the United States. Sterling is "
            "sensitive to Bank of England rate decisions, UK growth data, and the ongoing implications of "
            "Brexit on trade, financial services, and economic competitiveness."
        ),
        "macro": [
            "Bank of England vs. Fed rate differential: BoE cutting cycle pace vs. Fed stance drives near-term moves",
            "UK services inflation stickier than headline — constraining the pace of BoE rate cuts",
            "UK labour market data (wages, unemployment) is the primary BoE policy signal",
            "US dollar index (DXY) strength/weakness drives GBP/USD as much as UK-specific factors",
            "UK fiscal credibility and gilt market stability (2022 mini-budget memory) remains a Sterling risk factor",
        ],
        "geopolitical": [
            "UK-EU trade relationship post-Brexit limiting goods trade and creating ongoing tariff friction",
            "UK-US trade deal negotiations — potential catalyst for Sterling appreciation",
            "Financial services exports remain UK's largest trade surplus driver — EU market access is key",
            "Russia-Ukraine conflict energy impact raised UK energy import bills — structural current account headwind",
            "UK general election cycle and fiscal policy credibility directly affect gilt yields and Sterling",
        ],
        "outlook": (
            "GBP/USD direction hinges on the relative pace of BoE vs. Fed cutting cycles and UK growth "
            "resilience. Sterling has recovered significantly from 2022 lows but remains vulnerable to "
            "fiscal concerns, current account deficits, and any resurgence of US dollar strength."
        ),
    },
    "usdjpy": {
        "overview": (
            "USD/JPY is the most liquid dollar pair in Asian trading hours and the primary expression "
            "of global interest rate differentials. The yen's long weakness has been driven by the Bank "
            "of Japan's ultra-loose monetary policy — negative rates and yield curve control — in stark "
            "contrast to aggressive Fed tightening. Any BoJ policy normalisation is the defining macro event."
        ),
        "macro": [
            "BoJ yield curve control (YCC) policy and its gradual dismantling is the defining USD/JPY driver",
            "Massive US-Japan interest rate differential historically correlated with yen weakness",
            "Japan's export competitiveness benefits from weak yen — policy normalisation is politically complex",
            "Japanese government bond (JGB) market stability is a prerequisite for BoJ tightening",
            "Risk-off events (equity selloffs, geopolitical crises) typically trigger yen appreciation (safe haven)",
        ],
        "geopolitical": [
            "Japan's deep security alliance with the US limits geopolitical divergence in FX policy",
            "Ministry of Finance FX intervention threat: BoJ/MoF have intervened at 150+ levels historically",
            "China economic slowdown directly affects Japan's export-sensitive economy and JPY",
            "US-China trade tensions create indirect JPY safe-haven demand in Asia-Pacific risk-off episodes",
            "North Korea and Taiwan Strait risks are the primary regional geopolitical JPY safe-haven catalysts",
        ],
        "outlook": (
            "USD/JPY's structural direction is set by the convergence of Fed cuts and BoJ rate normalisation. "
            "As the differential narrows, yen appreciation pressure builds. The risk is that BoJ moves faster "
            "than the market expects — triggering an unwinding of yen carry trades and sharp JPY strength."
        ),
    },
    "usdcnh": {
        "overview": (
            "USD/CNH is the offshore Chinese yuan rate, traded in Hong Kong and globally, distinct from "
            "the onshore CNY which is managed within a daily band by the People's Bank of China. CNH "
            "reflects market pricing of China's economic trajectory, PBoC policy stance, capital flows, "
            "and the state of US-China trade and geopolitical relations."
        ),
        "macro": [
            "PBoC daily fixing (midpoint rate) is the primary CNH anchor — deviations signal policy intent",
            "China's export surplus and capital account controls limit but do not eliminate market-driven moves",
            "US-China interest rate differential and relative economic momentum drive directional bias",
            "Chinese property sector deleveraging and deflationary pressures weigh on yuan appreciation",
            "PBoC reserve requirement ratio and liquidity injections directly affect CNH market conditions",
        ],
        "geopolitical": [
            "US-China trade tariffs and technology export controls are the dominant geopolitical CNH driver",
            "Taiwan Strait tensions create episodic risk-off selling pressure on offshore yuan",
            "BRICS de-dollarisation efforts and yuan internationalisation are long-term structural themes",
            "Chinese capital controls limiting offshore yuan supply — PBoC directly manages the exchange rate",
            "Belt and Road Initiative lending and yuan settlement agreements gradually expanding CNH usage",
        ],
        "outlook": (
            "USD/CNH is less a free market than a managed expression of PBoC policy intent. The yuan's "
            "direction depends on whether China prioritises export competitiveness (weak yuan) or capital "
            "inflow attraction and internationalisation (stable/strong yuan). US tariff escalation is the "
            "primary near-term risk to a sharper CNH depreciation."
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
    "wti": {
        "overview": (
            "WTI (West Texas Intermediate) is the primary US crude oil benchmark, priced at "
            "Cushing, Oklahoma and traded as the NYMEX CL futures contract. As the lighter, "
            "sweeter counterpart to Brent, WTI reflects domestic shale production dynamics, "
            "inventory levels at Cushing, and Gulf Coast export infrastructure. It typically "
            "trades at a small discount to Brent, with the Brent-WTI spread fluctuating based "
            "on US export logistics, refinery demand, and global supply-demand balance."
        ),
        "macro": [
            "US shale (Permian, Bakken, Eagle Ford) output at record highs — naturally capping price upside",
            "Cushing, Oklahoma storage levels are the primary near-term WTI price indicator",
            "US Strategic Petroleum Reserve releases and refills directly impact domestic supply balance",
            "Refinery utilisation rates and crack spreads determine how quickly crude is converted to products",
            "Fed rate policy and USD strength are inversely correlated with commodity prices including WTI",
        ],
        "geopolitical": [
            "OPEC+ production quota decisions set the global supply floor affecting WTI via arbitrage",
            "Russia-Ukraine conflict and G7 price cap on Russian crude reshaping global trade flows",
            "Middle East tensions (Iran, Houthi Red Sea attacks) embed a persistent risk premium",
            "Mexico's Pemex production decline reducing heavy crude alternatives available to US refiners",
            "Gulf Coast export terminal capacity increasingly linking WTI to global Brent pricing",
        ],
        "outlook": (
            "WTI trades alongside Brent with added sensitivity to US-specific supply factors: shale output, "
            "Cushing storage, and Gulf export capacity. The Brent-WTI spread is the key structural variable — "
            "widening signals US pipeline bottlenecks; narrowing reflects growing US export integration. "
            "OPEC+ cohesion, Middle East escalation risk, and US shale economics remain the three dominant "
            "price-setting forces for the remainder of 2025."
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
    "rbobgas": {
        "overview": (
            "RBOB Gasoline (Reformulated Blendstock for Oxygenate Blending) is the primary US gasoline "
            "futures benchmark, traded on the NYMEX. Prices directly determine retail pump prices across "
            "the United States and are driven by crude oil input costs, refinery runs, seasonal blending "
            "specification changes, and regional supply-demand dynamics."
        ),
        "macro": [
            "Crude oil cost (~55-60% of gasoline price) is the dominant input — Brent and WTI moves flow through",
            "US refinery utilisation rates determine how quickly crude is converted to gasoline inventory",
            "Summer driving season (May-Sep) drives seasonal demand peaks and blending spec upgrades",
            "Ethanol blend mandates (RVP standards) create spring price spikes as summer-spec product is produced",
            "Consumer discretionary spending and vehicle miles traveled are the underlying demand indicators",
        ],
        "geopolitical": [
            "OPEC+ production decisions affect crude input costs and cascade into gasoline retail prices",
            "Gulf Coast refinery concentration (Texas, Louisiana) — hurricane season creates supply disruption risk",
            "US Strategic Petroleum Reserve releases can rapidly ease gasoline supply tightness",
            "Russia-Ukraine conflict raised global crude costs, contributing to 2022 pump price records",
            "US-China trade tensions affecting freight costs and indirectly influencing energy complex pricing",
        ],
        "outlook": (
            "RBOB prices track crude oil input costs with a refinery margin overlay. Near-term direction "
            "is set by WTI/Brent moves, US refinery run rates, and seasonal demand patterns. The structural "
            "long-term headwind is EV adoption gradually eroding gasoline demand in the developed world."
        ),
    },
    "heatingoil": {
        "overview": (
            "Heating Oil (HO=F, NYMEX No. 2 Fuel Oil) is a distillate fuel product used for residential "
            "heating and as a proxy for diesel and jet fuel pricing. It is the most weather-sensitive "
            "energy futures contract, with winter demand spikes in the US Northeast and Europe directly "
            "driving sharp seasonal price moves."
        ),
        "macro": [
            "Winter heating demand in the US Northeast (largest consuming region) is the primary seasonal driver",
            "Distillate inventories (diesel + heating oil) at Cushing and PADD 1 are the key supply signal",
            "Diesel demand from trucking and freight tracks industrial production and consumer goods flows",
            "Jet fuel demand recovery post-COVID structurally tightened the distillate complex",
            "Refinery crack spreads (HO vs. crude) reflect margin environment and refinery incentive to produce",
        ],
        "geopolitical": [
            "Russia's diesel export bans (2023) significantly tightened European distillate markets",
            "Middle East conflict risk raises crude input costs that flow through to heating oil prices",
            "EU sanctions on Russian refined products forced European buyers into Atlantic Basin alternatives",
            "Houthi Red Sea attacks disrupting tanker routes raised freight costs for distillate shipments",
            "Cold snap forecasts in the US Northeast routinely trigger sharp heating oil price spikes",
        ],
        "outlook": (
            "Heating oil prices are set by crude input costs plus the distillate crack spread. The structural "
            "bull case is tight global diesel supply from sanctions on Russian exports and rising jet fuel demand. "
            "Weather volatility in the US Northeast remains the primary short-term price catalyst."
        ),
    },
    "aluminium": {
        "overview": (
            "Aluminium is the world's most widely used non-ferrous metal, with applications spanning "
            "packaging, automotive, aerospace, construction, and the energy transition. China produces "
            "over 55% of global supply, making PBOC policy, power costs, and Chinese industrial activity "
            "the dominant price drivers. Smelting is intensely energy-intensive — power costs account for "
            "30-40% of production costs globally."
        ),
        "macro": [
            "China's smelting capacity (~55% of global supply) and power tariff policy are the primary supply drivers",
            "Energy cost is ~30-40% of aluminium production cost — power price spikes directly hit margins",
            "EV lightweighting megatrend increasing aluminium content per vehicle vs. traditional steel",
            "Solar panel frames and mounting structures creating structural new demand from renewable buildout",
            "LME warehouse stock levels and cancelled warrants are the key near-term price indicators",
        ],
        "geopolitical": [
            "Russian RUSAL accounts for ~6% of global supply — Western sanctions created significant market dislocation",
            "China's electricity rationing policies (during grid stress periods) directly constrain smelter output",
            "US and EU import tariffs on Chinese aluminium products redirecting trade flows",
            "Guinea bauxite supply (the primary alumina feedstock) is a critical single-country risk",
            "EU Carbon Border Adjustment Mechanism (CBAM) raising costs of high-carbon aluminium imports",
        ],
        "outlook": (
            "Aluminium's long-term demand outlook is structurally positive from lightweighting and energy transition "
            "applications. Near-term prices remain hostage to Chinese smelter output decisions and power costs. "
            "The RUSAL sanctions overhang and Guinea bauxite concentration create persistent supply-side tail risks."
        ),
    },
    "palladium": {
        "overview": (
            "Palladium is a platinum-group metal primarily used in catalytic converters for petrol (gasoline) "
            "engine vehicles, where it converts harmful exhaust emissions. Over 80% of annual supply comes "
            "from Russia and South Africa, creating extreme concentration risk. The EV transition represents "
            "the dominant long-term structural headwind as internal combustion engine volumes decline."
        ),
        "macro": [
            "Petrol vehicle catalytic converter demand accounts for ~80% of annual palladium consumption",
            "EV market share growth is the primary structural headwind — no palladium needed in battery vehicles",
            "Global auto production volumes (SAAR data) are the key leading demand indicator",
            "Palladium historically traded at a large premium to platinum; that premium has been narrowing",
            "Physical deficit markets in 2019-2022 pushed prices above $3,000/oz; structural surplus now emerging",
        ],
        "geopolitical": [
            "Russia (Norilsk Nickel) supplies ~40% of global palladium — Western sanctions created major supply risk",
            "South Africa supplies ~35-40% — power outages (load-shedding) and labour disputes are recurring risks",
            "Any escalation of Russia-Ukraine conflict or new sanctions directly threaten palladium supply chains",
            "Auto manufacturers have been building palladium inventories as supply security buffers since 2022",
            "EU and US emission standards (Euro 7, EPA Tier 3) driving catalyst technology efficiency improvements",
        ],
        "outlook": (
            "Palladium faces a structural demand decline as EV penetration erodes petrol vehicle production volumes. "
            "The market is transitioning from deficit to surplus, which is the primary long-term price headwind. "
            "Near-term, Russian supply disruption risk and auto production cycles remain the key price catalysts."
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
    "ethereum": "ethereum price market DeFi ETF regulation economic",
    "gold":     "gold price market central bank inflation economic",
    "silver":   "silver price market industrial demand supply",
    "copper":   "copper price market China demand supply",
    "platinum": "platinum price market hydrogen fuel cell supply South Africa",
    "eurusd":   "EUR USD euro dollar exchange rate ECB Fed",
    "gbpusd":   "GBP USD pound dollar exchange rate Bank of England",
    "usdjpy":   "USD JPY yen dollar exchange rate Bank of Japan",
    "usdcnh":   "USD CNH yuan dollar exchange rate China PBoC",
    "brent":      "brent crude oil price OPEC energy supply",
    "wti":        "WTI crude oil price OPEC energy supply United States",
    "henryhub":   "natural gas price LNG market Henry Hub",
    "ttfgas":     "European TTF gas price energy market supply",
    "rbobgas":    "RBOB gasoline price fuel refinery energy market",
    "heatingoil": "heating oil diesel price distillate energy market",
    "aluminium":  "aluminium aluminum price China smelter LME supply",
    "palladium":  "palladium price autocatalyst Russia supply EV",
}
