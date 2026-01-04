# FPL Brain - Project Context

## Overview
An xG-based FPL recommendation engine targeting a top 100 finish. Data-driven captain picks, transfer suggestions, Starting XI optimization, and chip timing without watching every game.

## User Profile
- FPL Team ID: 5033680
- Risk tolerance: Aggressive (take hits if gain > 4 pts over 3 GWs)
- Planning horizon: 4 gameweeks for transfers, 6+ for chip planning
- Currently mid-season (started GW20+), needs to catch up

## Repo & Hosting
- GitHub: madansh/fpl-brain
- Live: https://fplbrain.netlify.app
- Deploys automatically via Netlify on any commit

## Architecture
```
GitHub Actions (daily 6am UTC)
    │
    ▼
scripts/projections.py (Python)
    │ - Fetches FPL API + Understat xG data
    │ - Calculates projections + xMin
    │ - Generates recommendations + Starting XI
    ▼
public/data/*.json
    │
    ▼
React frontend reads JSON (no backend)
    │
    ▼
Netlify serves static site
```

## Key Files
| File | Purpose |
|------|---------|
| `scripts/projections.py` | Core engine - fetches data, calculates xG/xMin projections, outputs JSON |
| `src/App.jsx` | React frontend with Overview/Starting XI/Chips/Squad/Players tabs |
| `.github/workflows/daily-update.yml` | GitHub Action for daily automation |
| `requirements.txt` | Python deps: `requests>=2.32.0`, `understatapi>=0.7.0` |
| `public/data/recommendations.json` | Captain picks, transfer recs, chip alerts |
| `public/data/my_team.json` | User's squad with projections |
| `public/data/projections.json` | Top players by position |
| `public/data/starting_xi.json` | Starting XI recommendations for GW+1 to GW+6 |

## Current State (v3.1)

### Core Features (v3)
- ✅ Real xG/xA data from Understat via `understatapi` package
- ✅ Team strength calculated from actual xGA (not FPL's arbitrary ratings)
- ✅ Fuzzy name matching to link FPL players → Understat profiles
- ✅ Fixture difficulty based on opponent's real defensive record
- ✅ Captain picks with ownership %, differential flags, DGW indicators
- ✅ Data quality badges (✓ xG data vs ~ estimated)

### v3 Transfer Logic (Level 2)
- ✅ Only suggests replacing STARTERS (not bench fodder)
- ✅ Weights individual fixtures (not just averages)
- ✅ Includes form trend (hot 🔥 / cold 🥶)
- ✅ Flags players with upcoming DGWs
- ✅ Points-per-million value score
- ✅ Respects 3-player team limit
- ✅ Shows sell reasons (injury, form, fixtures, blanks)
- ✅ Shows buy reasons (DGW, form, easy fixtures)
- ✅ Net hit value calculation (worth -4?)

### v3 Chip Strategy Optimizer
- ✅ Bench Boost: finds best DGW based on bench coverage
- ✅ Triple Captain: finds premium with best DGW fixtures
- ✅ Free Hit: identifies BGW with poor squad coverage
- ✅ Wildcard: triggers on multiple issues (injuries, poor DGW coverage, cold players)
- ✅ Shows confidence level (HIGH/MEDIUM)
- ✅ Specific action needed for each chip

### v3.1 xMin + Starting XI (NEW)
- ✅ xMin calculation: `base_mins × availability × rotation_factor × form_factor`
- ✅ Known rotation risks database (Pep players, etc.)
- ✅ Effective projection = `projected_pts × (xMin/90)`
- ✅ Starting XI optimizer for GW+1 through GW+6
- ✅ Formation optimizer (tests all 8 valid FPL formations)
- ✅ Auto-captain selection based on effective pts
- ✅ Bench ordering for auto-sub priority
- ✅ GW alerts for blank exposure and low xMin issues
- ✅ Visual xMin bars in UI (green ≥80, yellow 60-79, red <60)
- ✅ New "Starting XI" tab in the app

## Configuration Constants (in projections.py)
```python
TEAM_ID = 5033680
PLANNING_HORIZON = 4  # GWs for transfer optimization
HIT_THRESHOLD_GWS = 3  # Aggressive: hit worth it if gain > 4 over 3 GWs
FORM_WEIGHT = 0.6     # 60% recent form, 40% season average
DECAY_FACTOR = 0.85   # Each older match weighted 15% less

# Rotation risks (reduce xMin for these players)
ROTATION_RISKS = {
    'high': ['Foden', 'Stones', 'Gvardiol', 'Grealish', 'Doku', 'Nkunku', 'Sterling', 'Neto'],
    'medium': ['Diaz', 'Gakpo', 'Jota', 'Rashford', 'Mount', 'Garnacho', 'Gordon', 'Barnes']
}

# Valid FPL formations
VALID_FORMATIONS = [
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2), 
    (4, 5, 1), (5, 2, 3), (5, 3, 2), (5, 4, 1)
]
```

## Planned Improvements (Priority Order)

### HIGH PRIORITY - Next Session

#### 1. Chip Strategy Without DGW Dependency
Current problem: Only triggers chips on detected DGW/BGW, but those are hard to predict
What to build:
- **Bench Boost**: Find GW where bench has highest (xMin × fixture_ease), even without DGW
- **Triple Captain**: Find GW where premium has easiest fixture + home + high xMin (DGW not required)
- **Free Hit**: Trigger on massive fixture swings or injury clusters, not just blanks
- **Wildcard**: Trigger on value bleeding, chip setup needs, fixture pivot points

#### 2. Blank/Double Prediction + Manual Override UI
Current problem: FPL API announces blanks very late (depends on cup results)
What to build:
- Automated prediction based on cup progress (teams in FA Cup/EFL Cup rounds = potential blank)
- Web scraping option: Pull Ben Crellin's spreadsheet or similar community source
- **In-app UI for manual override** (NOT raw JSON editing):
  - Simple form: "Add predicted blank: [GW dropdown] [Team multiselect]"
  - Simple form: "Add predicted double: [GW dropdown] [Team multiselect]"
  - Display current predictions with delete option
  - Store in localStorage
- Show confidence level: "Confirmed" vs "Predicted" vs "Possible"

### Medium Priority
3. **Level 3 Multi-Move Optimizer** - Consider 2-transfer combos, "Sell X+Y, buy A+B"
4. **Rolling 5-match xG** - Weight recent form more heavily (requires match-by-match Understat)
5. **Fixture difficulty visualization** - Calendar view like Legomane's graphics
6. **Transfer Logic v3** - Evaluate ALL 15 squad players for weak links, not just starters

### Lower Priority
7. **Backtesting module** - Validate model against 2019-2024 seasons
8. **Effective ownership** - Compare against top 10k, not overall
9. **What-if scenarios** - "What if I did transfer X instead?"
10. **Price change predictions** - Flag players likely to rise/fall
11. **Web scraping for community data** - Auto-pull from Ben Crellin, Legomane sources

## Known Limitations
- xG data is season-level from Understat (not match-by-match rolling)
- ~80% player match rate between FPL and Understat (fuzzy matching)
- Chip analysis depends on DGW/BGW being announced (FPL updates fixtures late)
- Transfer logic is single-move only (Level 3 multi-move coming)

## Key Context from User

### Blank/Double Gameweek Reality
- FPL only confirms blanks AFTER cup results (e.g., FA Cup, EFL Cup)
- Community sources (Ben Crellin, Legomane) predict blanks based on cup progress
- Example: GW31 blanks depend on semi-final results - Arsenal, City, Chelsea, Newcastle won SF so they WILL blank in GW31
- Blanks are "confirmed after second legs" - so predictions change as cups progress
- User doesn't have time to manually track this - needs automation or simple UI input

### Fixture Difficulty Sources
- Keep using Understat xGA for automated FDR calculation
- Legomane publishes visual FDR calendars on Twitter
- Color coding: Green = easy, Yellow = medium, Red = hard
- AFCON (Africa Cup of Nations) affects player availability in Jan-Feb

### User Preferences on Manual Input
- Does NOT want to edit raw JSON files
- Wants automation by default
- If manual input needed, wants simple UI abstracted away from code
- Time-constrained - can't constantly monitor Twitter for updates

### Useful Community Data Sources (for potential scraping)
- **Ben Crellin** (@BenCrellin) - Blank/Double predictions spreadsheet
- **Legomane** (@Legomane_FPL) - Fixture difficulty calendars, AFCON tracking

## Points Projection Formula
```
Projected Points = 
  (xG/90 × minutes_prob × goal_points / fixture_difficulty) +
  (xA/90 × minutes_prob × 3 / fixture_difficulty) +
  (team_CS_prob × CS_points) +
  appearance_points +
  bonus_estimate
```

## xMin Formula (NEW in v3.1)
```python
xMin = base_mins × availability × rotation_factor × form_factor

Where:
- base_mins = season_minutes / starts (capped at 90)
- availability = chance_of_playing / 100 (from FPL API)
- rotation_factor = 0.65 for high risk, 0.80 for medium, 1.0 for others
- form_factor = 1.05 if hot, 0.90 if cold, 1.0 if neutral

effective_pts = projected_pts × (xMin / 90)
```

## Troubleshooting
- **"No captain data"**: API might have returned empty, check Actions logs
- **Blank recommendations**: Check if `public/data/*.json` files exist
- **Netlify not updating**: Check if GitHub Action committed new files
- **Python errors**: Usually dependency issues, check `requirements.txt`
- **Starting XI not showing**: Check if `starting_xi.json` was generated

## Starting a New Claude Conversation
Paste this file or link to it and say:
"Continuing FPL Brain project. Context in CLAUDE_CONTEXT.md. Last session completed v3.1 with xMin and Starting XI. Ready to build: [Chip strategy without DGW / Blank prediction UI / Level 3 transfers]."
