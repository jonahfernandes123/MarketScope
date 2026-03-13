# MarketScope — Data Sources & Price Model

## Instrument Classification

### Instruments with real spot support

| Instrument | Price Type | Source        | Latency  | Notes |
|------------|------------|---------------|----------|-------|
| Bitcoin    | Spot       | Binance REST  | Real-time | Primary; CoinGecko fallback |
| Ethereum   | Spot       | Binance REST  | Real-time | Primary; CoinGecko fallback |
| EUR / USD  | FX Spot    | yfinance      | ~15 min  | Frankfurter ECB rate used as fallback only |
| GBP / USD  | FX Spot    | yfinance      | ~15 min  | Interbank composite via Yahoo |
| USD / JPY  | FX Spot    | yfinance      | ~15 min  | Interbank composite via Yahoo |
| USD / CNH  | FX Spot    | yfinance      | ~15 min  | Offshore CNH, not onshore CNY |

FX rates from yfinance are composite interbank quotes (not exchange-traded). They are
correctly labelled as **FX Spot** and are not futures prices.

---

### Instruments that are futures-only

| Instrument     | Exchange | Continuous Ticker | Front Month Contract | Curve Enabled |
|----------------|----------|-------------------|----------------------|---------------|
| Gold           | COMEX    | GC=F              | GCG/J/M/Q/V/Z+YY=F  | ✓ |
| Silver         | COMEX    | SI=F              | SIH/K/N/U/Z+YY=F    | ✓ |
| Copper         | COMEX    | HG=F              | HGH/K/N/U/Z+YY=F    | ✓ |
| Platinum       | NYMEX    | PL=F              | PLF/J/N/V+YY=F       | ✓ |
| Palladium      | NYMEX    | PA=F              | PAH/M/U/Z+YY=F       | ✓ |
| Brent Crude    | ICE      | BZ=F              | BZ+all months+YY=F   | ✓ |
| WTI Crude      | NYMEX    | CL=F              | CL+all months+YY=F   | ✓ |
| Henry Hub Gas  | NYMEX    | NG=F              | NG+all months+YY=F   | ✓ |
| RBOB Gasoline  | NYMEX    | RB=F              | RB+all months+YY=F   | ✓ |
| Heating Oil    | NYMEX    | HO=F              | HO+all months+YY=F   | ✓ |
| TTF Gas        | ICE      | TTF=F             | —                    | ✗ (see note) |
| Aluminium      | CME      | ALI=F             | —                    | ✗ (see note) |

**Why no spot price for metals/energy?**
- Gold/Silver LBMA spot (XAU, XAG) requires a paid data subscription (Refinitiv, Bloomberg).
- Physical crude oil spot (Dated Brent, WTI Midland) is an OTC assessment published by
  Platts/OPIS — no free API exists.
- Physical gas spot (NBP, Henry Hub cash) is OTC / exchange-published with a paid feed.

All metals and energy instruments display the **front-month continuous futures contract**
from yfinance. This is clearly labelled in the UI (e.g., "COMEX Front (GC=F)").

---

## Data Sources

| Source         | Used For                            | Latency        | Auth Required |
|----------------|-------------------------------------|----------------|---------------|
| Binance REST   | BTC/ETH spot price                  | Real-time       | No            |
| CoinGecko API  | BTC/ETH spot fallback + chart data  | ~30s (cached)   | No            |
| yfinance       | All futures, FX spot, chart history | ~15 min delayed | No            |
| Frankfurter    | EUR/USD fallback (ECB daily)        | Daily (EOD)     | No            |
| Yahoo Finance  | News articles                       | Variable        | No            |
| Google News    | Market context headlines            | Variable        | No            |

---

## Price Status Labels

The UI shows a colour-coded dot on each market card:

| Status      | Colour | Meaning |
|-------------|--------|---------|
| Live        | Green  | Real-time feed (Binance only) |
| Delayed     | Amber  | ~15-minute delayed data (yfinance) |
| Settlement  | Grey   | Official daily settlement or fixing |
| Unavailable | Red    | No price data (cold start / persistent error) |

---

## Term Structure / Forward Curve

- Available for: Gold, Silver, Copper, Platinum, Palladium, Brent, WTI, Henry Hub,
  RBOB Gasoline, Heating Oil.
- **Not available for:** TTF Gas (ICE individual months not reliably in yfinance),
  Aluminium (CME ALI individual contract coverage is incomplete in yfinance),
  all FX pairs, Bitcoin, Ethereum.
- Symbol format: `{ROOT}{MONTH_CODE}{YY}=F` — e.g., `CLJ26=F` = WTI April 2026.
- All curve prices are last-traded prices from yfinance (~15-min delayed).
- Curve state (Contango / Backwardation / Flat) is computed from the F1→F2 spread.
  Flat = less than 0.05% spread between front and second contract.
- Server-side cache: 5 minutes per instrument.

---

## Assumptions & Limitations

1. **yfinance contract availability**: Not all upcoming contract months are listed in
   yfinance (especially back-month contracts). Contracts with no data are shown as
   "unavailable" in the curve; the chart uses only contracts with valid prices.

2. **Brent crude (BZ=F) intraday data quality**: Yahoo Finance's BZ=F intraday feed
   occasionally returns stale or wrong-contract prices. A 20% sanity check against
   the daily close is applied; intraday data failing this check is discarded and the
   daily close is used instead.

3. **Continuous vs. front-month contracts**: The dashboard uses the continuous
   contract (e.g., `GC=F`) for live price display. This auto-rolls to the next
   contract at expiry. The `change_1d` calculation is anchored to the most recent
   prior-session daily close to avoid roll-distorted moves.

4. **FX rates**: yfinance FX composite quotes are interbank mid rates, not
   executable prices. They are marked as "FX Spot" rather than "Spot" to
   reflect this distinction.

5. **No environment variables required**: All data sources are free, public APIs
   with no authentication. The only env var used by the app is `SECRET_KEY`
   (for Flask session signing) and `USERS_*` (for login credentials).
