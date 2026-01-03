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

## Current State (v2)
- ✅ Real xG/xA data from Understat via `understatapi` package
- ✅ Team strength calculated from actual xGA (not FPL's arbitrary ratings)
- ✅ Fuzzy name matching to link FPL players → Understat profiles
- ✅ Fixture difficulty based on opponent's real defensive record
- ✅ Captain picks with ownership % and differential flags
- ✅ Transfer recommendations with net -4 hit value calculation
- ✅ DGW/BGW detection with chip alerts
- ✅ Data quality badges (✓ xG data vs ~ estimated)

## Configuration Constants (in projections.py)
```python
TEAM_ID = 5033680
PLANNING_HORIZON = 4  # GWs for transfer optimization
HIT_THRESHOLD_GWS = 3  # Aggressive: hit worth it if gain > 4 over 3 GWs
FORM_WEIGHT = 0.6     # 60% recent form, 40% season average
DECAY_FACTOR = 0.85   # Each older match weighted 15% less
```

## Planned Improvements (Priority Order)

### High Priority
1. **Rolling 5-match xG** - Weight recent form more heavily, not just season totals
2. **Chip strategy optimizer** - Specific recommendations for when to use BB/TC/FH/WC based on fixture swings and squad structure
3. **Form trend detection** - Identify players on hot/cold streaks

### Medium Priority
4. **Penalty/set piece taker identification** - Bonus xG for designated takers
5. **Minutes prediction** - Model rotation risk (especially for Pep's team)
6. **Fixture ticker** - Show next 6 fixtures color-coded by difficulty

### Lower Priority
7. **Backtesting module** - Validate model against 2019-2024 seasons
8. **Effective ownership** - Compare against top 10k, not overall ownership
9. **What-if scenarios** - "What if I did transfer X instead?"
10. **Price change predictions** - Flag players likely to rise/fall

## Known Limitations
- xG data is season-level from Understat (not match-by-match rolling)
- ~80% player match rate between FPL and Understat (fuzzy matching)
- No rotation risk modeling yet
- Chip recommendations are alerts only, not optimized timing

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
