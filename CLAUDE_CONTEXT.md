# FPL Brain - Project Context

## Overview
An xG-based FPL recommendation engine targeting a top 100 finish. Data-driven captain picks, transfer suggestions, and chip timing without watching every game.

## User Profile
- FPL Team ID: 5033680
- Risk tolerance: Aggressive (take hits if gain > 4 pts over 3 GWs)
- Planning horizon: 4 gameweeks for transfers, 6+ for chip planning
- Currently mid-season (started GW20+), needs to catch up

## Repo & Hosting
- GitHub: [your-username]/fpl-brain
- Live: https://fplbrain.netlify.app
- Deploys automatically via Netlify on any commit

## Architecture
```
GitHub Actions (daily 6am UTC)
    │
    ▼
scripts/projections.py (Python)
    │ - Fetches FPL API + Understat xG data
    │ - Calculates projections
    │ - Generates recommendations
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
| `scripts/projections.py` | Core engine - fetches data, calculates xG projections, outputs JSON |
| `src/App.jsx` | React frontend with Overview/Squad/Top Players tabs |
| `.github/workflows/daily-update.yml` | GitHub Action for daily automation |
| `requirements.txt` | Python deps: `requests>=2.32.0`, `understatapi>=0.7.0` |
| `public/data/recommendations.json` | Captain picks, transfer recs, chip alerts |
| `public/data/my_team.json` | User's squad with projections |
| `public/data/projections.json` | Top players by position |

## Current State (v3)
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

## Configuration Constants (in projections.py)
```python
TEAM_ID = 5033680
PLANNING_HORIZON = 4  # GWs for transfer optimization
HIT_THRESHOLD_GWS = 3  # Aggressive: hit worth it if gain > 4 over 3 GWs
FORM_WEIGHT = 0.6     # 60% recent form, 40% season average
DECAY_FACTOR = 0.85   # Each older match weighted 15% less
```

## Planned Improvements (Priority Order)

### HIGH PRIORITY - Next Session

#### 1. Transfer Logic v3 (Evaluate All 15 + xMin + Starting XI)
Current problem: Only evaluates starters, ignores rotation risk
What to build:
- Evaluate ALL 15 squad players, not just current starters
- Calculate xMin (expected minutes) per player:
  - `xMin = (season_minutes / starts) × availability_multiplier`
  - Reduce xMin for known rotation risks (Pep roulette, cup congestion)
- Effective projection = `xG_pts × (xMin / 90)`
- Output: Recommended Starting XI for each GW in planning horizon
- Transfer recs should avoid players with low xMin or upcoming blanks

#### 2. Chip Strategy Without DGW Dependency
Current problem: Only triggers chips on detected DGW/BGW, but those are hard to predict
What to build:
- **Bench Boost**: Find GW where bench has highest (xMin × fixture_ease), even without DGW
- **Triple Captain**: Find GW where premium has easiest fixture + home + high xMin (DGW not required - Haaland H vs Ipswich may beat a hard DGW)
- **Free Hit**: Trigger on massive fixture swings or injury clusters, not just blanks
- **Wildcard**: Trigger on value bleeding, chip setup needs, fixture pivot points

#### 3. Blank/Double Prediction + Manual Override UI
Current problem: FPL API announces blanks very late (depends on cup results)
What to build:
- Automated prediction based on cup progress (teams in FA Cup/EFL Cup rounds = potential blank)
- Web scraping option: Pull Ben Crellin's spreadsheet or similar community source
- **In-app UI for manual override** (NOT raw JSON editing):
  - Simple form: "Add predicted blank: [GW dropdown] [Team multiselect]"
  - Simple form: "Add predicted double: [GW dropdown] [Team multiselect]"
  - Display current predictions with delete option
  - Store in localStorage or simple backend
- Show confidence level: "Confirmed" vs "Predicted" vs "Possible"

#### 4. Starting XI Recommendation Per GW
New feature:
- For GW+1 through GW+6, show optimal starting XI based on fixtures
- Auto-pick captain and vice-captain
- Show bench order (first sub should be highest xPts among bench)
- Flag any GW where <11 players have fixtures (blank exposure)

### Medium Priority
5. **Level 3 Multi-Move Optimizer** - Consider 2-transfer combos, "Sell X+Y, buy A+B"
6. **Rolling 5-match xG** - Weight recent form more heavily (requires match-by-match Understat)
7. **Rotation risk database** - Flag Pep players, players with cup commitments, AFCON etc.
8. **Fixture difficulty visualization** - Calendar view like Legomane's graphics

### Lower Priority
9. **Backtesting module** - Validate model against 2019-2024 seasons
10. **Effective ownership** - Compare against top 10k, not overall
11. **What-if scenarios** - "What if I did transfer X instead?"
12. **Price change predictions** - Flag players likely to rise/fall
13. **Web scraping for community data** - Auto-pull from Ben Crellin, Legomane sources

## Known Limitations
- xG data is season-level from Understat (not match-by-match rolling)
- ~80% player match rate between FPL and Understat (fuzzy matching)
- No rotation risk modeling yet
- Chip analysis depends on DGW/BGW being announced (FPL updates fixtures)
- Transfer logic is single-move only (Level 3 multi-move coming next)

## Points Projection Formula
```
Projected Points = 
  (xG/90 × minutes_prob × goal_points / fixture_difficulty) +
  (xA/90 × minutes_prob × 3 / fixture_difficulty) +
  (team_CS_prob × CS_points) +
  appearance_points +
  bonus_estimate
```

## Troubleshooting
- **"No captain data"**: API might have returned empty, check Actions logs
- **Blank recommendations**: Check if `public/data/*.json` files exist
- **Netlify not updating**: Check if GitHub Action committed new files
- **Python errors**: Usually dependency issues, check `requirements.txt`

## Starting a New Claude Conversation
Paste this file or link to it and say:
"Continuing FPL Brain project. Context in CLAUDE_CONTEXT.md. Last worked on [X]. Ready to add [Y]."
