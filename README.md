# ING Stocks

**ING Stocks** is a custom Home Assistant integration to fetch **stock and ETF data by ISIN**
using ING’s public instrument API.

The integration is inspired by the original *ING Stocks* integration by **RalfEs73**,
but has been **completely rebuilt and extended** with modern Home Assistant best practices
(DataUpdateCoordinator, Options Flow, dynamic sensors).

---

## ✨ Features

- 📈 Fetch **stock & ETF prices** by ISIN
- 🔄 **Configurable scan interval per instrument** (changeable later via Options)
- 🧠 Automatic or manual **instrument type selection**:
  - `auto` (API / name-based detection)
  - `ETF`
  - `Stock`
- 📊 Optional **key figures** (only created if available):
  - Dividend yield
  - P/E ratio
  - Market capitalization
  - 52-week high / low
- 🎨 **Consistent Material Design icons**
  - Dynamic up/down icons for price changes
  - Clear ETF vs. stock distinction
- ⚡ Efficient polling using **DataUpdateCoordinator**
- 📉 Works perfectly with **ApexCharts Card**
- 🧩 HACS-ready

---

## 📦 Installation (via HACS – Custom Repository)

1. Open **HACS**
2. Go to **Integrations**
3. Click **⋮ → Custom repositories**
4. Add:
   - **Repository:**  
     `https://github.com/marq24/ha-ingstocks`
   - **Type:** Integration
5. Install **ING Stocks**
6. **Restart Home Assistant**

---

## ⚙️ Configuration

1. Go to **Settings → Devices & Services**
2. Click **Add Integration**
3. Search for **ING Stocks**
4. Enter:
   - **ISIN** (required)
   - **Name** (optional)
   - **Scan interval** (minutes)
   - **Instrument type**:
     - Automatic
     - ETF
     - Stock

> Example ISIN: `IE0008GRJRO8`

---

## 🔧 Options (after setup)

Open the integration options (⚙️) to change:
- Display name
- Scan interval
- Instrument type (auto / ETF / stock)

Changes take effect immediately after reload.

---

## 🧪 Sensors Created

The following sensors are created **per ISIN** (depending on availability):

| Sensor | Description |
|------|-------------|
| `price` | Last traded price |
| `change_percent` | Price change in percent |
| `change_absolute` | Absolute price change |
| `last_update` | Timestamp of last update |
| `dividend_yield` | Dividend yield *(if available)* |
| `price_earnings_ratio` | P/E ratio *(if available)* |
| `market_capitalization` | Market capitalization *(if available)* |
| `52w_low` | 52-week low *(if available)* |
| `52w_high` | 52-week high *(if available)* |

> If key figures are not available for an instrument, the related sensors are **not created**.

---

## 📊 Example: ApexCharts Card

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Vanguard FTSE All-World UCITS ETF
  show_states: true
  colorize_states: true

graph_span: 1d

series:
  - entity: sensor.vanguard_ftse_all_world_ucits_etf_preis
    name: Price
    type: line
    extend_to: false
    group_by:
      duration: 5min
      func: last
      fill: last
```

---

## ⚠️ Notes & Limitations

- Not all instruments provide key figures
- Scan intervals should be chosen responsibly  
  (recommended: **5–30 minutes**)
- The integration uses an **unofficial public API**
  and is **not affiliated with ING**

---

## 🙏 Credits

- Inspired by **ING Stocks** by *RalfEs73*
- Developed independently by **Sundancer78**

---

## 🐛 Issues & Feedback

Please report issues or ideas via GitHub:

👉 https://github.com/marq24/ha-ingstocks/issues


## Changelog

### 1.2.0
- Added quantity option (float)
- Added calculated position value sensor

### 1.1.1
- Bugfix: attribute handling aligned with original ING Stocks integration

