"""
FPL Brain - Projection Engine v4.0
- Real xG from Understat
- Smarter transfer logic with form, fixtures, DGW awareness
- Chip strategy optimizer (BB/TC/FH/WC timing)
- xMin calculation + Starting XI recommendations

v4.0 Changes:
- Fixed Understat matching (>= 0.6 threshold, team_title key, multi-name matching)
- Improved transfer logic (MIN_BUY_PROJECTION, higher gain threshold, ownership penalty)
- Added rolling 5-match form calculation
- Enhanced injury news parsing
- Chip strategy works without DGW (fixture-based triggers)
"""

import requests
import json
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
from collections import defaultdict
from understatapi import UnderstatClient

# =============================================================================
# CONFIGURATION
# =============================================================================

TEAM_ID = 5033680
PLANNING_HORIZON = 4
HIT_THRESHOLD_GWS = 3
FORM_WEIGHT = 0.6
DECAY_FACTOR = 0.85

# Transfer logic thresholds (v4.0)
MIN_BUY_PROJECTION = 15       # Don't recommend players under 15 pts/4GW
SELL_THRESHOLD_4GW = 10       # Only sell if < 10 pts/4GW (was 12)
MIN_GAIN_THRESHOLD = 3        # Only recommend if gain > 3 pts (was 1)
OWNERSHIP_WEIGHT = 0.1        # Small penalty for template players (>30% owned)

BASE_URL = "https://fantasy.premierleague.com/api"
BOOTSTRAP_URL = f"{BASE_URL}/bootstrap-static/"
FIXTURES_URL = f"{BASE_URL}/fixtures/"
TEAM_URL = f"{BASE_URL}/entry/{TEAM_ID}/"
PICKS_URL = f"{BASE_URL}/entry/{TEAM_ID}/event/{{gw}}/picks/"
HISTORY_URL = f"{BASE_URL}/entry/{TEAM_ID}/history/"
PLAYER_URL = f"{BASE_URL}/element-summary/{{player_id}}/"

PTS_GOAL = {1: 6, 2: 6, 3: 5, 4: 4}
PTS_ASSIST = 3
PTS_CLEAN_SHEET = {1: 4, 2: 4, 3: 1, 4: 0}
PTS_APPEARANCE = 2

# Known rotation risks - update as season progresses
ROTATION_RISKS = {
    'high': ['Foden', 'Stones', 'Gvardiol', 'Grealish', 'Doku', 'Nkunku', 'Sterling', 'Neto'],
    'medium': ['Diaz', 'Gakpo', 'Jota', 'Rashford', 'Mount', 'Garnacho', 'Gordon', 'Barnes']
}

# Valid FPL formations: (DEF, MID, FWD) - GK is always 1
VALID_FORMATIONS = [
    (3, 4, 3), (3, 5, 2), (4, 3, 3), (4, 4, 2), 
    (4, 5, 1), (5, 2, 3), (5, 3, 2), (5, 4, 1)
]

# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_json(url):
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_understat_data():
    print("Fetching Understat xG data...")
    try:
        understat = UnderstatClient()
        player_data = understat.league(league="EPL").get_player_data(season="2024")
        team_data = understat.league(league="EPL").get_team_data(season="2024")
        return player_data, team_data
    except Exception as e:
        print(f"Error fetching Understat data: {e}")
        return None, None


def match_player_names(fpl_player, understat_players, team_name_map):
    """
    Improved matching using multiple name fields and team normalization.
    Fixes: threshold >= 0.6, team_title key, multi-name matching.
    """
    # Use all available name fields
    web_name = fpl_player.get('web_name', '').lower().strip()
    first_name = fpl_player.get('first_name', '').lower().strip()
    second_name = fpl_player.get('second_name', '').lower().strip()
    full_name = f"{first_name} {second_name}".strip()
    fpl_team_id = fpl_player.get('team')

    # Normalize team names (FPL -> Understat)
    TEAM_NORMALIZE = {
        'man city': 'manchester city',
        'man utd': 'manchester united',
        'spurs': 'tottenham',
        'newcastle': 'newcastle united',
        "nott'm forest": 'nottingham forest',
    }
    fpl_team = team_name_map.get(fpl_team_id, '').lower()
    normalized_team = TEAM_NORMALIZE.get(fpl_team, fpl_team)

    best_match = None
    best_score = 0

    for us_player in understat_players:
        us_name = us_player.get('player_name', '').lower()
        us_team = us_player.get('team_title', '').lower()  # Fix: was 'team_name'

        # Team filter with normalization
        if normalized_team and normalized_team not in us_team:
            continue

        # Try multiple matching strategies
        scores = [
            SequenceMatcher(None, full_name, us_name).ratio(),      # Full name
            SequenceMatcher(None, web_name, us_name).ratio(),       # Web name
        ]

        # Surname matching
        if second_name:
            us_name_parts = us_name.split()
            if us_name_parts:
                scores.append(SequenceMatcher(None, second_name, us_name_parts[-1]).ratio())

        # Boost if surname matches exactly (handles "Salah" in "Mohamed Salah")
        if second_name and second_name in us_name:
            scores.append(0.85)

        # Boost for substring matches
        if web_name in us_name or (us_name.split() and us_name.split()[-1] == web_name):
            scores.append(0.85)

        score = max(scores)

        if score >= 0.6 and score > best_score:  # Fix: >= not >
            best_score = score
            best_match = us_player

    return best_match


# =============================================================================
# ENHANCED DATA SOURCES (v4.0)
# =============================================================================

def get_player_history(player_id):
    """Fetch detailed player history from FPL API."""
    url = PLAYER_URL.format(player_id=player_id)
    return fetch_json(url)


def calculate_rolling_form(history, matches=5):
    """Calculate rolling xGI-equivalent from recent FPL match history."""
    if not history:
        return {'rolling_form': 0, 'trend': 'neutral', 'matches_used': 0}

    recent = history[-matches:] if len(history) >= matches else history
    if not recent:
        return {'rolling_form': 0, 'trend': 'neutral', 'matches_used': 0}

    # Calculate weighted recent performance
    total_pts = 0
    total_xgi_proxy = 0
    weights = [1.0, 0.95, 0.85, 0.75, 0.65]  # More recent = higher weight

    for i, match in enumerate(reversed(recent)):
        weight = weights[i] if i < len(weights) else 0.5
        pts = float(match.get('total_points', 0))
        goals = int(match.get('goals_scored', 0))
        assists = int(match.get('assists', 0))
        xgi_proxy = goals * 0.9 + assists * 0.6  # Rough xGI approximation

        total_pts += pts * weight
        total_xgi_proxy += xgi_proxy * weight

    weighted_avg = total_pts / len(recent)

    # Determine trend by comparing recent half to older half
    if len(recent) >= 4:
        recent_half = sum(m.get('total_points', 0) for m in recent[-2:]) / 2
        older_half = sum(m.get('total_points', 0) for m in recent[:2]) / 2
        if recent_half > older_half * 1.25:
            trend = 'rising'
        elif recent_half < older_half * 0.75:
            trend = 'falling'
        else:
            trend = 'stable'
    else:
        trend = 'neutral'

    return {
        'rolling_form': round(weighted_avg, 2),
        'rolling_xgi': round(total_xgi_proxy / len(recent), 3),
        'trend': trend,
        'matches_used': len(recent),
    }


def parse_injury_news(news):
    """
    Parse FPL news field to determine injury severity.
    Returns: severity score (0=healthy, 1=minor, 2=moderate, 3=severe)
    """
    if not news:
        return {'severity': 0, 'category': 'healthy', 'parsed': None}

    news_lower = news.lower()

    # Severe - likely out for extended period
    severe_keywords = ['surgery', 'acl', 'mcl', 'broken', 'fracture', 'season',
                       'months', 'long-term', 'ruled out']
    for kw in severe_keywords:
        if kw in news_lower:
            return {'severity': 3, 'category': 'severe', 'parsed': news}

    # Moderate - likely out for a few weeks
    moderate_keywords = ['hamstring', 'groin', 'muscle', 'strain', 'weeks',
                         'scan', 'assessment', 'knock']
    for kw in moderate_keywords:
        if kw in news_lower:
            return {'severity': 2, 'category': 'moderate', 'parsed': news}

    # Minor - doubtful but might play
    minor_keywords = ['doubt', 'fitness', 'ill', 'sick', 'minor', 'dead leg',
                      'precaution', 'managed']
    for kw in minor_keywords:
        if kw in news_lower:
            return {'severity': 1, 'category': 'minor', 'parsed': news}

    # Unknown news - treat as minor concern
    return {'severity': 1, 'category': 'unknown', 'parsed': news}


def calculate_price_trend(history):
    """Analyze recent price changes to detect risers/fallers."""
    if not history or 'history' not in history:
        return {'trend': 'stable', 'recent_change': 0}

    matches = history['history']
    if len(matches) < 3:
        return {'trend': 'stable', 'recent_change': 0}

    # Get price from last 5 matches
    recent_prices = [m.get('value', 0) for m in matches[-5:]]
    if not recent_prices or recent_prices[0] == 0:
        return {'trend': 'stable', 'recent_change': 0}

    price_change = recent_prices[-1] - recent_prices[0]

    if price_change >= 3:  # 0.3m rise
        trend = 'rising_fast'
    elif price_change >= 1:
        trend = 'rising'
    elif price_change <= -3:
        trend = 'falling_fast'
    elif price_change <= -1:
        trend = 'falling'
    else:
        trend = 'stable'

    return {'trend': trend, 'recent_change': price_change / 10}


def get_enhanced_player_data(player_id, player):
    """Fetch and calculate additional real-time data for a player."""
    history_data = get_player_history(player_id)

    if not history_data:
        return {
            'rolling_5_form': {'rolling_form': 0, 'trend': 'neutral'},
            'news_severity': parse_injury_news(player.get('news', '')),
            'price_trend': {'trend': 'stable', 'recent_change': 0},
        }

    match_history = history_data.get('history', [])
    rolling_form = calculate_rolling_form(match_history, matches=5)
    news_severity = parse_injury_news(player.get('news', ''))
    price_trend = calculate_price_trend(history_data)

    return {
        'rolling_5_form': rolling_form,
        'news_severity': news_severity,
        'price_trend': price_trend,
    }


# =============================================================================
# FIXTURE ANALYSIS (DGW/BGW Detection)
# =============================================================================

def analyze_fixtures(fixtures, teams, current_gw):
    team_lookup = {t['id']: t for t in teams}
    
    gw_range = range(current_gw, current_gw + 10)
    team_fixtures = {t['id']: {gw: [] for gw in gw_range} for t in teams}
    gw_fixture_counts = defaultdict(int)
    
    for f in fixtures:
        gw = f.get('event')
        if not gw or gw < current_gw or gw >= current_gw + 10:
            continue
        
        gw_fixture_counts[gw] += 1
        
        home_id = f['team_h']
        away_id = f['team_a']
        
        team_fixtures[home_id][gw].append({
            'opponent_id': away_id,
            'opponent': team_lookup.get(away_id, {}).get('short_name', '?'),
            'is_home': True,
            'finished': f.get('finished', False),
        })
        
        team_fixtures[away_id][gw].append({
            'opponent_id': home_id,
            'opponent': team_lookup.get(home_id, {}).get('short_name', '?'),
            'is_home': False,
            'finished': f.get('finished', False),
        })
    
    dgw_gws = [gw for gw, count in gw_fixture_counts.items() if count > 10]
    bgw_gws = [gw for gw, count in gw_fixture_counts.items() if count < 10]
    
    team_dgws = {t['id']: [] for t in teams}
    team_bgws = {t['id']: [] for t in teams}
    
    for team_id, gw_data in team_fixtures.items():
        for gw, fixtures_list in gw_data.items():
            if len(fixtures_list) >= 2:
                team_dgws[team_id].append(gw)
            elif len(fixtures_list) == 0:
                team_bgws[team_id].append(gw)
    
    return {
        'team_fixtures': team_fixtures,
        'dgw_gws': dgw_gws,
        'bgw_gws': bgw_gws,
        'team_dgws': team_dgws,
        'team_bgws': team_bgws,
        'gw_counts': dict(gw_fixture_counts),
    }


# =============================================================================
# TEAM STRENGTH
# =============================================================================

def calculate_team_strengths(understat_teams, fpl_teams):
    team_strength = {}
    
    name_map = {
        'Arsenal': 'Arsenal', 'Aston Villa': 'Aston Villa', 'Bournemouth': 'Bournemouth',
        'Brentford': 'Brentford', 'Brighton': 'Brighton', 'Chelsea': 'Chelsea',
        'Crystal Palace': 'Crystal Palace', 'Everton': 'Everton', 'Fulham': 'Fulham',
        'Ipswich': 'Ipswich', 'Leicester': 'Leicester', 'Liverpool': 'Liverpool',
        'Man City': 'Manchester City', 'Man Utd': 'Manchester United',
        'Newcastle': 'Newcastle United', "Nott'm Forest": 'Nottingham Forest',
        'Southampton': 'Southampton', 'Spurs': 'Tottenham', 'West Ham': 'West Ham',
        'Wolves': 'Wolverhampton Wanderers'
    }
    
    for fpl_team in fpl_teams:
        team_id = fpl_team['id']
        fpl_name = fpl_team['name']
        us_name = name_map.get(fpl_name, fpl_name)
        
        us_team = None
        if understat_teams:
            for t_id, t_data in understat_teams.items():
                if t_data.get('title', '').lower() == us_name.lower():
                    us_team = t_data
                    break
        
        if us_team and 'history' in us_team:
            history = us_team['history']
            if history:
                total_xg = sum(float(h.get('xG', 0)) for h in history)
                total_xga = sum(float(h.get('xGA', 0)) for h in history)
                games = len(history)
                
                xg_per_game = total_xg / games if games > 0 else 1.3
                xga_per_game = total_xga / games if games > 0 else 1.3
                cs_prob = max(0.05, min(0.5, 0.6 - (xga_per_game * 0.25)))
                
                team_strength[team_id] = {
                    'name': fpl_name,
                    'short_name': fpl_team['short_name'],
                    'xg_per_game': round(xg_per_game, 2),
                    'xga_per_game': round(xga_per_game, 2),
                    'cs_prob': round(cs_prob, 3),
                    'attack_strength': xg_per_game / 1.3,
                    'defense_strength': xga_per_game / 1.3,
                }
                continue
        
        team_strength[team_id] = {
            'name': fpl_name,
            'short_name': fpl_team['short_name'],
            'xg_per_game': 1.3,
            'xga_per_game': 1.3,
            'cs_prob': 0.25,
            'attack_strength': 1.0,
            'defense_strength': 1.0,
        }
    
    return team_strength


def get_fixture_difficulty(team_strengths, opponent_id, is_home):
    opp = team_strengths.get(opponent_id, {})
    opp_defense = opp.get('defense_strength', 1.0)
    home_boost = 0.9 if is_home else 1.1
    difficulty = opp_defense * home_boost
    return max(0.6, min(1.5, difficulty))


# =============================================================================
# FORM ANALYSIS
# =============================================================================

def calculate_form_score(player):
    form = float(player.get('form', 0) or 0)
    points_per_game = float(player.get('points_per_game', 0) or 0)
    
    if points_per_game > 0:
        form_ratio = form / points_per_game
        if form_ratio > 1.3:
            trend = 'hot'
        elif form_ratio < 0.7:
            trend = 'cold'
        else:
            trend = 'neutral'
    else:
        trend = 'neutral'
    
    return {'form': form, 'ppg': points_per_game, 'trend': trend}


# =============================================================================
# PLAYER PROJECTIONS
# =============================================================================

def calculate_player_xgi(fpl_player, understat_match, team_strengths):
    if not understat_match:
        mins = int(fpl_player.get('minutes', 0) or 0)
        if mins < 90:
            return None
        goals = int(fpl_player.get('goals_scored', 0) or 0)
        assists = int(fpl_player.get('assists', 0) or 0)
        creativity = float(fpl_player.get('creativity', 0) or 0)
        return {
            'xg_p90': (goals / mins) * 90,
            'xa_p90': (assists / mins) * 90,
            'npxg_p90': (goals / mins) * 90,
            'shots_p90': (goals * 3 / mins) * 90,
            'key_passes_p90': (creativity / 100 / mins) * 90,
            'minutes': mins,
            'games': int(fpl_player.get('starts', 1) or 1),
            'data_quality': 'approximated'
        }
    
    mins = float(understat_match.get('time', 0))
    games = int(understat_match.get('games', 0))
    
    if mins < 90 or games < 1:
        return None
    
    xg = float(understat_match.get('xG', 0))
    xa = float(understat_match.get('xA', 0))
    npxg = float(understat_match.get('npxG', 0))
    shots = int(understat_match.get('shots', 0))
    key_passes = int(understat_match.get('key_passes', 0))
    
    return {
        'xg_p90': (xg / mins) * 90,
        'xa_p90': (xa / mins) * 90,
        'npxg_p90': (npxg / mins) * 90,
        'shots_p90': (shots / mins) * 90,
        'key_passes_p90': (key_passes / mins) * 90,
        'minutes': mins,
        'games': games,
        'total_xgi': xg + xa,
        'data_quality': 'understat'
    }


def project_gameweek_points(player, xgi_stats, fixture_difficulty, 
                            opponent_cs_prob, element_type, team_cs_prob,
                            is_dgw=False):
    if xgi_stats is None:
        return 0
    
    chance = player.get('chance_of_playing_next_round')
    if chance is not None and chance < 50:
        return 0
    availability = (chance / 100) if chance is not None else 0.95
    
    avg_mins = xgi_stats.get('minutes', 0) / max(1, xgi_stats.get('games', 1))
    mins_prob = min(1.0, avg_mins / 70)
    
    xg_adj = xgi_stats['xg_p90'] / fixture_difficulty
    xa_adj = xgi_stats['xa_p90'] / fixture_difficulty
    
    goal_pts = xg_adj * PTS_GOAL.get(element_type, 4)
    assist_pts = xa_adj * PTS_ASSIST
    cs_pts = team_cs_prob * PTS_CLEAN_SHEET.get(element_type, 0)
    appearance_pts = PTS_APPEARANCE if mins_prob > 0.6 else 1
    
    xgi = xg_adj + xa_adj
    if element_type in [1, 2]:
        bonus_pts = min(3, xgi * 1.5 + (team_cs_prob * 1.5))
    else:
        bonus_pts = min(3, xgi * 2.5) if xgi > 0.25 else 0
    
    total = goal_pts + assist_pts + cs_pts + appearance_pts + bonus_pts
    multiplier = 2 if is_dgw else 1
    
    return round(total * availability * mins_prob * multiplier, 2)


# =============================================================================
# xMIN CALCULATION + STARTING XI (NEW in v3.1)
# =============================================================================

def calculate_xmin(player, player_proj, player_history=None):
    """
    Calculate expected minutes (xMin) for a player.
    xMin = base_minutes × availability × rotation_factor × form_factor
    """
    mins = float(player.get('minutes', 0) or 0)
    starts = int(player.get('starts', 0) or 0)
    
    # Base xMin from season average
    if starts > 0:
        avg_mins_per_start = mins / starts
    elif mins > 0:
        avg_mins_per_start = min(90, mins / max(1, mins // 60))
    else:
        avg_mins_per_start = 0
    
    base_xmin = min(90, avg_mins_per_start)
    
    # Availability multiplier from FPL API
    chance = player.get('chance_of_playing_next_round')
    if chance is not None:
        availability = float(chance) / 100
    else:
        status = player.get('status', 'a')
        availability = 1.0 if status == 'a' else 0.5 if status == 'd' else 0.0
    
    # Rotation risk factor
    name = player.get('web_name', '')
    if name in ROTATION_RISKS['high']:
        rotation_factor = 0.65
    elif name in ROTATION_RISKS['medium']:
        rotation_factor = 0.80
    else:
        rotation_factor = 1.0
    
    # Form factor
    form_trend = player_proj.get('form_trend', 'neutral') if player_proj else 'neutral'
    if form_trend == 'hot':
        form_factor = 1.05
    elif form_trend == 'cold':
        form_factor = 0.90
    else:
        form_factor = 1.0
    
    xmin = base_xmin * availability * rotation_factor * form_factor
    return round(min(90, max(0, xmin)), 1)


def calculate_effective_pts(projected_pts, xmin):
    """Effective projection = projected_pts × (xMin / 90)"""
    if xmin <= 0:
        return 0
    return round(projected_pts * (xmin / 90), 2)


def select_optimal_xi(squad_with_projections, gw, fixture_data):
    """
    Select optimal Starting XI respecting FPL formation rules.
    Returns: (starting_xi, bench, formation, total_score)
    """
    available = []
    unavailable = []
    
    for p in squad_with_projections:
        team_id = p['team_id']
        gw_fixtures = fixture_data['team_fixtures'].get(team_id, {}).get(gw, [])
        
        if not gw_fixtures:
            p['gw_status'] = 'blank'
            unavailable.append(p)
            continue
        
        if p.get('xmin', 0) < 10:
            p['gw_status'] = 'unlikely'
            unavailable.append(p)
            continue
        
        p['gw_status'] = 'available'
        available.append(p)
    
    # Group by position
    by_pos = {1: [], 2: [], 3: [], 4: []}
    for p in available:
        by_pos[p['position']].append(p)
    
    for pos in by_pos:
        by_pos[pos].sort(key=lambda x: x.get('effective_pts', 0), reverse=True)
    
    # Find best valid formation
    best_xi = None
    best_score = -1
    best_formation = None
    
    for def_c, mid_c, fwd_c in VALID_FORMATIONS:
        if len(by_pos[1]) < 1: continue
        if len(by_pos[2]) < def_c: continue
        if len(by_pos[3]) < mid_c: continue
        if len(by_pos[4]) < fwd_c: continue
        
        xi = [by_pos[1][0]]
        xi.extend(by_pos[2][:def_c])
        xi.extend(by_pos[3][:mid_c])
        xi.extend(by_pos[4][:fwd_c])
        
        score = sum(p.get('effective_pts', 0) for p in xi)
        
        if score > best_score:
            best_score = score
            best_xi = xi
            best_formation = f"{def_c}-{mid_c}-{fwd_c}"
    
    if not best_xi:
        all_sorted = sorted(available, key=lambda x: x.get('effective_pts', 0), reverse=True)
        best_xi = all_sorted[:11]
        best_formation = "?"
    
    xi_ids = {p['player_id'] for p in best_xi}
    bench = [p for p in available if p['player_id'] not in xi_ids]
    bench.extend(unavailable)
    bench.sort(key=lambda x: x.get('effective_pts', 0), reverse=True)
    
    return best_xi, bench[:4], best_formation, best_score


def generate_starting_xi_recommendations(my_picks, players, projections, 
                                          fixture_data, team_strengths, next_gw):
    """Generate Starting XI recommendations for GW+1 through GW+6."""
    player_lookup = {p['id']: p for p in players}
    recommendations = []
    
    for gw in range(next_gw, next_gw + 6):
        squad = []
        for pick in my_picks:
            pid = pick['element']
            player = player_lookup.get(pid, {})
            proj = projections.get(pid, {})
            
            gw_fixtures = proj.get('fixtures', [])
            gw_proj = next((f for f in gw_fixtures if f.get('gw') == gw), {})
            gw_pts = gw_proj.get('projected_pts', 0)
            
            xmin = calculate_xmin(player, proj)
            eff_pts = calculate_effective_pts(gw_pts, xmin)
            
            squad.append({
                'player_id': pid,
                'name': player.get('web_name', pick.get('web_name', 'Unknown')),
                'position': player.get('element_type', pick.get('element_type', 0)),
                'team_id': player.get('team', pick.get('team_id', 0)),
                'team': team_strengths.get(player.get('team', 0), {}).get('short_name', '?'),
                'xmin': xmin,
                'projected_pts': round(gw_pts, 2),
                'effective_pts': eff_pts,
                'fixture': gw_proj.get('opponent', '?'),
                'difficulty': gw_proj.get('difficulty', 1.0),
                'is_dgw': gw_proj.get('is_dgw', False),
                'is_bgw': gw_proj.get('is_bgw', False),
                'selling_price': pick.get('selling_price', 0) / 10,
            })
        
        xi, bench, formation, total_eff = select_optimal_xi(squad, gw, fixture_data)
        
        xi_sorted = sorted(xi, key=lambda x: x['effective_pts'], reverse=True)
        captain = xi_sorted[0] if xi_sorted else None
        vice = xi_sorted[1] if len(xi_sorted) > 1 else None
        
        blank_count = sum(1 for p in squad if p.get('is_bgw'))
        low_xmin_count = sum(1 for p in squad if p.get('xmin', 0) < 60)
        
        recommendations.append({
            'gameweek': gw,
            'formation': formation,
            'total_effective_pts': round(total_eff, 1),
            'captain': {
                'name': captain['name'],
                'team': captain['team'],
                'effective_pts': captain['effective_pts'],
                'xmin': captain['xmin'],
                'fixture': captain['fixture'],
            } if captain else None,
            'vice_captain': {
                'name': vice['name'],
                'effective_pts': vice['effective_pts'],
            } if vice else None,
            'starting_xi': [
                {
                    'name': p['name'],
                    'position': ['GK', 'DEF', 'MID', 'FWD'][p['position'] - 1],
                    'team': p['team'],
                    'effective_pts': p['effective_pts'],
                    'projected_pts': p['projected_pts'],
                    'xmin': p['xmin'],
                    'fixture': p['fixture'],
                    'difficulty': p['difficulty'],
                    'is_dgw': p['is_dgw'],
                }
                for p in sorted(xi, key=lambda x: (x['position'], -x['effective_pts']))
            ],
            'bench': [
                {
                    'name': p['name'],
                    'position': ['GK', 'DEF', 'MID', 'FWD'][p['position'] - 1],
                    'effective_pts': p['effective_pts'],
                    'xmin': p['xmin'],
                    'status': p.get('gw_status', 'available'),
                    'bench_order': i + 1,
                }
                for i, p in enumerate(bench[:4])
            ],
            'alerts': {
                'blank_count': blank_count,
                'low_xmin_count': low_xmin_count,
                'needs_attention': blank_count >= 3 or low_xmin_count >= 4,
            }
        })
    
    return recommendations


# =============================================================================
# TRANSFER LOGIC v2
# =============================================================================

def get_transfer_recommendations(my_squad, all_players, projections, bank, 
                                  fixture_data, team_strengths, current_gw):
    recommendations = []
    
    squad_ids = {p['element'] for p in my_squad}
    squad_team_counts = defaultdict(int)
    for p in my_squad:
        squad_team_counts[p.get('team_id', 0)] += 1
    
    starters = [p for p in my_squad if p.get('multiplier', 0) > 0]
    
    starter_scores = []
    for pick in starters:
        player_id = pick['element']
        proj = projections.get(player_id, {})
        
        sell_score = 0
        reasons = []
        
        proj_4gw = proj.get('next_4gw_pts', 0)
        if proj_4gw < SELL_THRESHOLD_4GW:
            sell_score += 3
            reasons.append('low_projection')
        
        if proj.get('form_trend') == 'cold':
            sell_score += 2
            reasons.append('cold_form')
        
        chance = proj.get('chance_of_playing')
        if chance is not None and chance < 75:
            sell_score += 3
            reasons.append('injury_doubt')
        
        team_id = pick.get('team_id', 0)
        if team_id in fixture_data['team_bgws']:
            upcoming_blanks = [gw for gw in fixture_data['team_bgws'][team_id] 
                             if gw <= current_gw + 4]
            if upcoming_blanks:
                sell_score += 2
                reasons.append(f'blank_gw{upcoming_blanks[0]}')
        
        avg_difficulty = proj.get('avg_difficulty_4gw', 1.0)
        if avg_difficulty > 1.15:
            sell_score += 1
            reasons.append('hard_fixtures')
        
        starter_scores.append({
            'player_id': player_id,
            'name': pick.get('web_name', 'Unknown'),
            'position': pick.get('element_type', 0),
            'team_id': team_id,
            'selling_price': pick.get('selling_price', 0) / 10,
            'proj_4gw': proj_4gw,
            'sell_score': sell_score,
            'sell_reasons': reasons,
        })
    
    starter_scores.sort(key=lambda x: (-x['sell_score'], x['proj_4gw']))
    
    for weak in starter_scores[:3]:
        if weak['sell_score'] < 2:
            continue
        
        pos = weak['position']
        budget = bank + weak['selling_price']
        
        candidates = []
        for p in all_players:
            if p['id'] in squad_ids:
                continue
            if p['element_type'] != pos:
                continue
            
            cost = p['now_cost'] / 10
            if cost > budget:
                continue
            
            p_team = p['team']
            current_count = squad_team_counts.get(p_team, 0)
            if weak['team_id'] == p_team:
                current_count -= 1
            if current_count >= 3:
                continue
            
            proj = projections.get(p['id'], {})
            if not proj:
                continue

            # Skip players not getting minutes (v4.0 fix)
            recent_mins = int(p.get('minutes', 0) or 0)
            starts = int(p.get('starts', 0) or 0)
            if starts < 3 or recent_mins < 200:
                continue  # Not a regular starter

            # Skip cold form players - they're out of favor (v4.0 fix)
            if proj.get('form_trend') == 'cold':
                continue

            # Skip approximated data for transfers - unreliable (v4.0 fix)
            if proj.get('data_quality') == 'approximated':
                continue

            proj_4gw = proj.get('next_4gw_pts', 0)

            # Skip low quality players (v4.0)
            if proj_4gw < MIN_BUY_PROJECTION:
                continue

            gain_4gw = proj_4gw - weak['proj_4gw']

            # Skip marginal gains (v4.0)
            if gain_4gw < MIN_GAIN_THRESHOLD:
                continue

            buy_score = gain_4gw
            buy_reasons = []

            # Ownership penalty for template players (v4.0)
            player_ownership = float(p.get('selected_by_percent', 0) or 0)
            if player_ownership > 30:
                buy_score -= OWNERSHIP_WEIGHT * player_ownership
                buy_reasons.append('template_risk')
            
            if proj.get('form_trend') == 'hot':
                buy_score += 1.5
                buy_reasons.append('hot_form')
            
            p_team_id = p['team']
            upcoming_dgws = fixture_data['team_dgws'].get(p_team_id, [])
            dgw_in_range = [gw for gw in upcoming_dgws if gw <= current_gw + 6]
            if dgw_in_range:
                buy_score += 2
                buy_reasons.append(f'dgw{dgw_in_range[0]}')
            
            avg_diff = proj.get('avg_difficulty_4gw', 1.0)
            if avg_diff < 0.9:
                buy_score += 1
                buy_reasons.append('easy_fixtures')
            
            value = proj_4gw / cost if cost > 0 else 0
            
            candidates.append({
                'player': p,
                'proj_4gw': proj_4gw,
                'gain_4gw': round(gain_4gw, 1),
                'buy_score': buy_score,
                'buy_reasons': buy_reasons,
                'cost': cost,
                'value': round(value, 2),
                'fixtures': proj.get('fixture_preview', [])[:4],
            })
        
        candidates.sort(key=lambda x: -x['buy_score'])
        
        if candidates:
            best = candidates[0]
            p = best['player']
            proj = projections.get(p['id'], {})
            
            gain_4gw = best['gain_4gw']
            hit_value = gain_4gw - (4 * PLANNING_HORIZON / HIT_THRESHOLD_GWS)
            worth_hit = hit_value > 0
            
            recommendations.append({
                'priority': len(recommendations) + 1,
                'out_id': weak['player_id'],
                'out_name': weak['name'],
                'out_reasons': weak['sell_reasons'],
                'in_id': p['id'],
                'in_name': p['web_name'],
                'in_team': team_strengths.get(p['team'], {}).get('short_name', '?'),
                'in_cost': best['cost'],
                'gain_4gw': best['gain_4gw'],
                'buy_reasons': best['buy_reasons'],
                'worth_hit': worth_hit,
                'hit_value': round(hit_value, 1),
                'value_score': best['value'],
                'position': pos,
                'fixtures': best['fixtures'],
                'data_quality': proj.get('data_quality', 'unknown'),
            })
    
    return recommendations


# =============================================================================
# CHIP STRATEGY OPTIMIZER (v4.0 - Fixture-based triggers without DGW dependency)
# =============================================================================

def analyze_chip_strategy(my_squad, projections, fixture_data, team_strengths,
                          current_gw, chips_available):
    """
    Enhanced chip strategy that works even without confirmed DGW/BGW.
    Uses fixture difficulty and player projections to recommend optimal chip timing.
    """
    recommendations = []

    dgw_gws = fixture_data['dgw_gws']
    bgw_gws = fixture_data['bgw_gws']
    team_dgws = fixture_data['team_dgws']
    team_bgws = fixture_data['team_bgws']
    team_fixtures = fixture_data['team_fixtures']

    # Analyze all upcoming GWs for fixture-based triggers
    gw_range = range(current_gw, current_gw + 6)

    # ==========================================================================
    # BENCH BOOST - Works without DGW by analyzing bench quality + fixtures
    # ==========================================================================
    if 'bench_boost' in chips_available:
        best_bb_gw = None
        best_bb_score = 0
        bb_analysis = []

        # Analyze ALL gameweeks, not just DGWs
        for gw in gw_range:
            dgw_players = 0
            total_bench_proj = 0
            total_bench_xmin = 0
            fixture_ease_score = 0

            for pick in my_squad:
                team_id = pick.get('team_id', 0)
                is_bench = pick.get('multiplier', 0) == 0
                player_proj = projections.get(pick['element'], {})

                has_dgw = gw in team_dgws.get(team_id, [])
                gw_fixtures = team_fixtures.get(team_id, {}).get(gw, [])

                if has_dgw:
                    dgw_players += 1

                if is_bench and gw_fixtures:
                    # Get projected points for this specific GW
                    gw_proj = next((f for f in player_proj.get('fixtures', [])
                                   if f.get('gw') == gw), {})
                    pts = gw_proj.get('projected_pts', 2)
                    difficulty = gw_proj.get('difficulty', 1.0)

                    # Calculate fixture ease (lower difficulty = easier)
                    ease = max(0.5, 2.0 - difficulty)
                    total_bench_proj += pts
                    fixture_ease_score += ease

                    # Estimate xMin from player data
                    xmin = player_proj.get('xmin', 60) if player_proj else 60
                    total_bench_xmin += xmin

            # Score: bench points * fixture ease * (xMin factor) * DGW bonus
            xmin_factor = min(1.2, total_bench_xmin / 240)  # 4 bench players * 60 avg mins
            dgw_bonus = 1 + (dgw_players * 0.15)
            bb_score = total_bench_proj * (1 + fixture_ease_score / 4) * xmin_factor * dgw_bonus

            bb_analysis.append({
                'gw': gw,
                'dgw_players': dgw_players,
                'bench_proj': round(total_bench_proj, 1),
                'bench_xmin': round(total_bench_xmin, 0),
                'fixture_ease': round(fixture_ease_score, 2),
                'score': round(bb_score, 1),
                'is_dgw': gw in dgw_gws,
            })

            if bb_score > best_bb_score:
                best_bb_score = bb_score
                best_bb_gw = gw

        if best_bb_gw and best_bb_score > 8:  # Minimum threshold
            best = next(a for a in bb_analysis if a['gw'] == best_bb_gw)
            is_dgw = best['is_dgw']
            reasoning = f"GW{best_bb_gw} "
            if is_dgw:
                reasoning += f"is a DGW with {best['dgw_players']} players doubling. "
            else:
                reasoning += f"has favorable fixtures (ease: {best['fixture_ease']:.1f}). "
            reasoning += f"Projected bench value: {best['bench_proj']} pts."

            recommendations.append({
                'chip': 'Bench Boost',
                'recommended_gw': best_bb_gw,
                'confidence': 'HIGH' if (is_dgw and best['dgw_players'] >= 10) or best['score'] > 15 else 'MEDIUM',
                'reasoning': reasoning,
                'action_needed': f"Ensure bench has high xMin players with easy fixtures by GW{best_bb_gw}.",
                'analysis': sorted(bb_analysis, key=lambda x: -x['score'])[:5],
            })

    # ==========================================================================
    # TRIPLE CAPTAIN - Works without DGW by finding best premium fixture
    # ==========================================================================
    if 'triple_captain' in chips_available:
        best_tc_gw = None
        best_tc_player = None
        best_tc_score = 0
        tc_analysis = []

        premiums = [p for p in my_squad if p.get('selling_price', 0) / 10 >= 10]

        # Analyze ALL gameweeks for premium players
        for gw in gw_range:
            for pick in premiums:
                team_id = pick.get('team_id', 0)
                player_id = pick['element']
                player_name = pick.get('web_name', 'Unknown')
                proj = projections.get(player_id, {})

                gw_fixtures = team_fixtures.get(team_id, {}).get(gw, [])
                if not gw_fixtures:
                    continue

                # Calculate fixture quality
                total_diff = 0
                fixture_strs = []
                home_bonus = 0

                for fix in gw_fixtures:
                    diff = get_fixture_difficulty(team_strengths, fix['opponent_id'], fix['is_home'])
                    total_diff += diff
                    h_a = '(H)' if fix['is_home'] else '(A)'
                    fixture_strs.append(f"{fix['opponent']} {h_a}")
                    if fix['is_home']:
                        home_bonus += 0.1

                avg_diff = total_diff / len(gw_fixtures) if gw_fixtures else 1.0
                is_dgw = len(gw_fixtures) >= 2

                # Get projected points
                gw_proj = next((f for f in proj.get('fixtures', [])
                               if f.get('gw') == gw), {})
                base_pts = gw_proj.get('projected_pts', proj.get('next_gw_pts', 4))

                # xMin factor - higher xMin = more reliable captain
                xmin = proj.get('xmin', 85) if proj else 85
                xmin_factor = min(1.1, xmin / 85)

                # TC score: projected * 3 * ease * home_bonus * xmin_factor * dgw_bonus
                ease_mult = max(0.7, 2.0 - avg_diff)
                dgw_mult = 1.8 if is_dgw else 1.0
                tc_score = base_pts * 3 * ease_mult * (1 + home_bonus) * xmin_factor * dgw_mult

                tc_analysis.append({
                    'gw': gw,
                    'player': player_name,
                    'player_id': player_id,
                    'fixtures': fixture_strs,
                    'avg_difficulty': round(avg_diff, 2),
                    'is_home': any(f['is_home'] for f in gw_fixtures),
                    'is_dgw': is_dgw,
                    'projected_tc_pts': round(tc_score, 1),
                    'xmin': xmin,
                })

                if tc_score > best_tc_score:
                    best_tc_score = tc_score
                    best_tc_gw = gw
                    best_tc_player = player_name

        if best_tc_gw and best_tc_score > 15:  # Minimum threshold
            best = next(a for a in tc_analysis if a['gw'] == best_tc_gw and a['player'] == best_tc_player)
            reasoning = f"TC {best_tc_player} in GW{best_tc_gw} ({', '.join(best['fixtures'])})"
            if best['is_dgw']:
                reasoning += " - DOUBLE GAMEWEEK"
            elif best['is_home']:
                reasoning += " - HOME fixture"
            reasoning += f". Projected: {best['projected_tc_pts']:.0f} pts."

            recommendations.append({
                'chip': 'Triple Captain',
                'recommended_gw': best_tc_gw,
                'recommended_player': best_tc_player,
                'confidence': 'HIGH' if best['is_dgw'] or (best['avg_difficulty'] < 0.85 and best['is_home']) else 'MEDIUM',
                'reasoning': reasoning,
                'action_needed': f"Ensure {best_tc_player} is in your squad for GW{best_tc_gw}.",
                'analysis': sorted(tc_analysis, key=lambda x: -x['projected_tc_pts'])[:5],
            })

    # ==========================================================================
    # FREE HIT - Triggers on BGW OR fixture swings (hard -> easy for opponents)
    # ==========================================================================
    if 'free_hit' in chips_available:
        best_fh_gw = None
        best_fh_score = 0
        fh_analysis = []

        for gw in gw_range:
            players_with_fixtures = 0
            players_blanking = []
            squad_difficulty = 0
            hard_fixture_count = 0

            for pick in my_squad:
                team_id = pick.get('team_id', 0)
                gw_fixtures = team_fixtures.get(team_id, {}).get(gw, [])

                if gw_fixtures:
                    players_with_fixtures += 1
                    # Sum up fixture difficulties
                    for fix in gw_fixtures:
                        diff = get_fixture_difficulty(team_strengths, fix['opponent_id'], fix['is_home'])
                        squad_difficulty += diff
                        if diff > 1.1:  # Hard fixture
                            hard_fixture_count += 1
                else:
                    players_blanking.append(pick.get('web_name', 'Unknown'))

            # FH score: low coverage + high difficulty = good FH week
            blanking_penalty = (15 - players_with_fixtures) * 3
            difficulty_penalty = (squad_difficulty / max(1, players_with_fixtures) - 1.0) * 10
            fh_score = blanking_penalty + difficulty_penalty

            fh_analysis.append({
                'gw': gw,
                'players_with_fixtures': players_with_fixtures,
                'players_blanking': len(players_blanking),
                'blanking_names': players_blanking[:5],
                'avg_difficulty': round(squad_difficulty / max(1, players_with_fixtures), 2),
                'hard_fixtures': hard_fixture_count,
                'score': round(fh_score, 1),
                'is_bgw': gw in bgw_gws,
            })

            if fh_score > best_fh_score:
                best_fh_score = fh_score
                best_fh_gw = gw

        if best_fh_gw and best_fh_score > 5:  # Minimum threshold
            best = next(a for a in fh_analysis if a['gw'] == best_fh_gw)
            is_bgw = best['is_bgw']

            if is_bgw:
                reasoning = f"GW{best_fh_gw} is a BGW where only {best['players_with_fixtures']} of your players have fixtures."
            else:
                reasoning = f"GW{best_fh_gw} has difficult fixtures for your squad (avg difficulty: {best['avg_difficulty']:.2f}, {best['hard_fixtures']} hard games)."

            recommendations.append({
                'chip': 'Free Hit',
                'recommended_gw': best_fh_gw,
                'confidence': 'HIGH' if is_bgw and best['players_with_fixtures'] < 7 else 'MEDIUM',
                'reasoning': reasoning,
                'action_needed': f"Save Free Hit for GW{best_fh_gw}. Don't waste transfers preparing.",
                'players_blanking': best['blanking_names'] if best['blanking_names'] else None,
                'analysis': sorted(fh_analysis, key=lambda x: -x['score'])[:5],
            })

    # ==========================================================================
    # WILDCARD - Triggers on value bleeding, cold players, or fixture swings
    # ==========================================================================
    if 'wildcard' in chips_available:
        wc_triggers = []
        wc_score = 0

        # Count cold/out-of-form players
        cold_players = []
        for pick in my_squad:
            proj = projections.get(pick['element'], {})
            if proj.get('form_trend') == 'cold':
                wc_score += 1
                cold_players.append(pick.get('web_name', 'Unknown'))

        if len(cold_players) >= 3:
            wc_triggers.append(f'{len(cold_players)}_cold_players')

        # Check DGW coverage (if DGWs exist)
        dgw_coverage = 0
        if dgw_gws:
            for pick in my_squad:
                team_id = pick.get('team_id', 0)
                if any(gw in team_dgws.get(team_id, []) for gw in dgw_gws if gw > current_gw):
                    dgw_coverage += 1

            if dgw_coverage < 8:
                wc_score += 3
                wc_triggers.append('poor_dgw_coverage')

        # Count injuries/doubts
        injured = sum(1 for p in my_squad
                     if projections.get(p['element'], {}).get('chance_of_playing') is not None
                     and projections.get(p['element'], {}).get('chance_of_playing') < 75)
        if injured >= 3:
            wc_score += 2
            wc_triggers.append(f'{injured}_injuries')

        # Check for value bleeding (players losing value)
        value_loss = 0
        for pick in my_squad:
            proj = projections.get(pick['element'], {})
            price_trend = proj.get('price_trend', {})
            if isinstance(price_trend, dict) and price_trend.get('trend') in ['falling', 'falling_fast']:
                value_loss += 1

        if value_loss >= 4:
            wc_score += 2
            wc_triggers.append(f'{value_loss}_falling_prices')

        # Check for overall squad fixture difficulty in next 4 GWs
        total_4gw_difficulty = 0
        for pick in my_squad:
            proj = projections.get(pick['element'], {})
            total_4gw_difficulty += proj.get('avg_difficulty_4gw', 1.0)

        avg_squad_difficulty = total_4gw_difficulty / len(my_squad) if my_squad else 1.0
        if avg_squad_difficulty > 1.15:  # Hard upcoming fixtures
            wc_score += 2
            wc_triggers.append('hard_fixtures_ahead')

        if wc_score >= 3:
            # Find best WC timing
            best_wc_gw = current_gw + 1
            if dgw_gws:
                upcoming_dgws = [gw for gw in dgw_gws if gw > current_gw]
                if upcoming_dgws:
                    best_wc_gw = min(upcoming_dgws) - 1

            recommendations.append({
                'chip': 'Wildcard',
                'recommended_gw': best_wc_gw,
                'confidence': 'HIGH' if wc_score >= 5 else 'MEDIUM',
                'reasoning': f"Consider WC in GW{best_wc_gw} to fix squad issues: {', '.join(set(wc_triggers))}",
                'action_needed': "Restructure squad for better fixtures and form.",
                'triggers': wc_triggers,
                'cold_players': cold_players[:5] if cold_players else None,
            })

    return recommendations


# =============================================================================
# CAPTAIN SELECTION + DIFFERENTIAL ANALYSIS (v4.0)
# =============================================================================

def get_captain_picks(my_squad, projections, all_players, fixture_data, current_gw):
    """
    Enhanced captain selection with differential analysis.
    Calculates EO impact and risk/reward for each captain choice.
    """
    captain_options = []
    player_lookup = {p['id']: p for p in all_players}

    # Find template captains (highest owned premiums in the game)
    all_sorted_by_ownership = sorted(
        [(p['id'], float(p.get('selected_by_percent', 0)), p.get('web_name', ''))
         for p in all_players if p['now_cost'] >= 100],  # 10.0m+
        key=lambda x: -x[1]
    )
    template_captain_ids = [p[0] for p in all_sorted_by_ownership[:3]]
    template_captains = {p[0]: {'ownership': p[1], 'name': p[2]} for p in all_sorted_by_ownership[:3]}

    # Get template captain's projected points (for differential calc)
    template_proj_pts = max(
        projections.get(pid, {}).get('next_gw_pts', 0)
        for pid in template_captain_ids
    ) if template_captain_ids else 6.0

    for pick in my_squad:
        if pick.get('multiplier', 0) == 0:
            continue

        player_id = pick['element']
        proj = projections.get(player_id, {})
        player = player_lookup.get(player_id, {})

        proj_pts = proj.get('next_gw_pts', 0)
        if proj_pts > 2:
            ownership = float(player.get('selected_by_percent', 0))

            team_id = pick.get('team_id', player.get('team', 0))
            has_dgw = (current_gw + 1) in fixture_data['team_dgws'].get(team_id, [])

            # Calculate Effective Ownership (EO) - estimate of captain ownership
            # Higher owned players are more likely to be captained
            if ownership > 50:
                estimated_captain_pct = ownership * 0.6  # ~60% of owners captain
            elif ownership > 30:
                estimated_captain_pct = ownership * 0.4
            elif ownership > 15:
                estimated_captain_pct = ownership * 0.25
            else:
                estimated_captain_pct = ownership * 0.1

            # Differential value: points gained/lost vs template
            is_template = player_id in template_captain_ids
            diff_vs_template = proj_pts - template_proj_pts

            # Risk/reward calculation
            # Upside: If differential scores more than template
            # Downside: If template scores more than differential
            if is_template:
                upside = 0
                downside = 0
                risk_category = 'safe'
            else:
                # Upside = extra points * (100 - your EO)% of managers don't have this captain
                upside = max(0, diff_vs_template * 2) * (100 - estimated_captain_pct) / 100
                # Downside = lost points * template EO%
                template_eo = max(tc['ownership'] for tc in template_captains.values()) * 0.5
                downside = max(0, -diff_vs_template * 2) * template_eo / 100

                if upside > downside * 1.5:
                    risk_category = 'high_upside'
                elif downside > upside * 1.5:
                    risk_category = 'risky'
                else:
                    risk_category = 'balanced'

            captain_options.append({
                'player_id': player_id,
                'name': player.get('web_name', 'Unknown'),
                'team': proj.get('team', '?'),
                'projected_pts': proj_pts,
                'doubled_pts': round(proj_pts * 2, 1),
                'fixture': proj.get('next_fixture', ''),
                'fixture_difficulty': proj.get('next_fixture_diff', 1.0),
                'ownership': ownership,
                'estimated_captain_pct': round(estimated_captain_pct, 1),
                'form': player.get('form', '0'),
                'form_trend': proj.get('form_trend', 'neutral'),
                'is_differential': ownership < 15,
                'is_template': is_template,
                'has_dgw': has_dgw,
                'data_quality': proj.get('data_quality', 'unknown'),
                # Differential analysis
                'diff_vs_template': round(diff_vs_template, 2),
                'upside_pts': round(upside, 1),
                'downside_pts': round(downside, 1),
                'risk_category': risk_category,
            })

    captain_options.sort(key=lambda x: (-x['has_dgw'], -x['projected_pts']))

    # Generate differential recommendation
    safe_pick = captain_options[0] if captain_options else None

    # Find best differential: low ownership with analysis vs safe pick
    differential_picks = []
    if safe_pick:
        safe_pts = safe_pick['projected_pts']
        safe_eo = safe_pick['estimated_captain_pct']

        for c in captain_options[1:]:  # Skip safe pick
            if c['ownership'] < 20:  # Low ownership = differential
                pts_diff = c['projected_pts'] - safe_pts
                eo_advantage = safe_eo - c['estimated_captain_pct']

                # Calculate risk/reward
                # If diff hauls (2x expected): you gain eo_advantage % on field
                # If safe hauls (2x expected): you lose eo_advantage % on field
                haul_scenario = c['projected_pts'] * 2  # If they score double projected
                safe_haul = safe_pts * 2

                # Risk assessment
                if pts_diff >= 0:
                    risk_level = 'low_risk'  # Diff projects same or better
                elif pts_diff >= -2:
                    risk_level = 'medium_risk'  # Within 2 pts
                else:
                    risk_level = 'high_risk'  # More than 2 pts behind

                differential_picks.append({
                    **c,
                    'vs_safe_diff': round(pts_diff, 2),
                    'eo_advantage': round(eo_advantage, 1),
                    'risk_level': risk_level,
                    'haul_upside': round(eo_advantage * 0.15, 1),  # Approx rank gain if diff hauls
                })

    # Best differential: highest projected among low ownership
    best_differential = None
    if differential_picks:
        differential_picks.sort(key=lambda x: -x['projected_pts'])
        best_differential = differential_picks[0]

    return {
        'picks': captain_options[:5],
        'safe_pick': safe_pick,
        'differential_pick': best_differential,
        'all_differentials': differential_picks[:3],  # Top 3 differential options
        'template_captains': [
            {'name': tc['name'], 'ownership': tc['ownership'], 'projected': projections.get(pid, {}).get('next_gw_pts', 0)}
            for pid, tc in template_captains.items()
        ],
    }


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_projections():
    print("=" * 60)
    print("FPL BRAIN v4.0 - Projection Engine")
    print("=" * 60)
    
    print("\nFetching FPL data...")
    bootstrap = fetch_json(BOOTSTRAP_URL)
    fixtures = fetch_json(FIXTURES_URL)
    
    if not bootstrap or not fixtures:
        print("Failed to fetch FPL data!")
        return
    
    players = bootstrap['elements']
    teams = bootstrap['teams']
    events = bootstrap['events']
    
    understat_players, understat_teams = get_understat_data()
    
    current_gw = next((e['id'] for e in events if e['is_current']), 1)
    next_gw = next((e['id'] for e in events if e['is_next']), current_gw + 1)
    print(f"Current GW: {current_gw}, Next GW: {next_gw}")
    
    print("Analyzing fixtures for DGW/BGW...")
    fixture_data = analyze_fixtures(fixtures, teams, next_gw)
    print(f"  DGWs detected: {fixture_data['dgw_gws']}")
    print(f"  BGWs detected: {fixture_data['bgw_gws']}")
    
    team_strengths = calculate_team_strengths(understat_teams, teams)
    team_lookup = {t['id']: t for t in teams}
    team_name_map = {t['id']: t['name'] for t in teams}
    
    print("Calculating projections...")
    projections = {}
    matched_count = 0
    
    for player in players:
        player_id = player['id']
        team_id = player['team']
        element_type = player['element_type']
        
        us_match = None
        if understat_players:
            us_match = match_player_names(
                player, understat_players, team_name_map
            )
            if us_match:
                matched_count += 1
        
        xgi_stats = calculate_player_xgi(player, us_match, team_strengths)
        if xgi_stats is None:
            continue
        
        form_data = calculate_form_score(player)
        team_fixtures = fixture_data['team_fixtures'].get(team_id, {})
        team_cs_prob = team_strengths.get(team_id, {}).get('cs_prob', 0.2)
        team_dgws = fixture_data['team_dgws'].get(team_id, [])
        
        gw_projections = []
        total_difficulty = 0
        fixture_preview = []
        
        for gw in range(next_gw, next_gw + 6):
            gw_fixtures = team_fixtures.get(gw, [])
            is_dgw = len(gw_fixtures) >= 2
            is_bgw = len(gw_fixtures) == 0
            
            if is_bgw:
                gw_projections.append({
                    'gw': gw, 'projected_pts': 0, 'opponent': 'BLANK',
                    'is_home': False, 'difficulty': 0, 'is_dgw': False, 'is_bgw': True
                })
                fixture_preview.append({'gw': gw, 'fixture': 'BLANK', 'difficulty': 0})
                continue
            
            gw_pts = 0
            gw_opponents = []
            gw_difficulty = 0
            
            for fix in gw_fixtures:
                opp_id = fix['opponent_id']
                diff = get_fixture_difficulty(team_strengths, opp_id, fix['is_home'])
                opp_cs = team_strengths.get(opp_id, {}).get('cs_prob', 0.2)
                
                pts = project_gameweek_points(
                    player, xgi_stats, diff, opp_cs, element_type, team_cs_prob,
                    is_dgw=False
                )
                gw_pts += pts
                gw_difficulty += diff
                
                h_a = '(H)' if fix['is_home'] else '(A)'
                gw_opponents.append(f"{fix['opponent']} {h_a}")
            
            avg_diff = gw_difficulty / len(gw_fixtures)
            total_difficulty += avg_diff
            
            gw_projections.append({
                'gw': gw,
                'projected_pts': round(gw_pts, 2),
                'opponent': ', '.join(gw_opponents),
                'is_home': gw_fixtures[0]['is_home'] if gw_fixtures else False,
                'difficulty': round(avg_diff, 2),
                'is_dgw': is_dgw,
                'is_bgw': False,
            })
            
            fixture_preview.append({
                'gw': gw,
                'fixture': ', '.join(gw_opponents),
                'difficulty': round(avg_diff, 2),
                'is_dgw': is_dgw,
            })
        
        next_fix = gw_projections[0] if gw_projections else {}
        non_blank_gws = [g for g in gw_projections[:4] if not g.get('is_bgw')]
        avg_difficulty_4gw = (total_difficulty / len(non_blank_gws)) if non_blank_gws else 1.0
        
        # Parse injury news for severity (v4.0 quick win)
        injury_info = parse_injury_news(player.get('news', ''))

        projections[player_id] = {
            'player_id': player_id,
            'name': player['web_name'],
            'team': team_lookup.get(team_id, {}).get('short_name', '?'),
            'team_id': team_id,
            'position': element_type,
            'price': player['now_cost'] / 10,
            'ownership': player['selected_by_percent'],
            'form': player['form'],
            'form_trend': form_data['trend'],
            'news': player.get('news', ''),
            'news_severity': injury_info['severity'],
            'news_category': injury_info['category'],
            'chance_of_playing': player.get('chance_of_playing_next_round'),
            'xg_p90': round(xgi_stats.get('xg_p90', 0), 3),
            'xa_p90': round(xgi_stats.get('xa_p90', 0), 3),
            'next_gw_pts': next_fix.get('projected_pts', 0),
            'next_fixture': next_fix.get('opponent', '?'),
            'next_fixture_diff': next_fix.get('difficulty', 1.0),
            'has_dgw_soon': bool(team_dgws),
            'dgw_gws': team_dgws,
            'next_4gw_pts': round(sum(g['projected_pts'] for g in gw_projections[:4]), 1),
            'next_6gw_pts': round(sum(g['projected_pts'] for g in gw_projections[:6]), 1),
            'avg_difficulty_4gw': round(avg_difficulty_4gw, 2),
            'fixtures': gw_projections,
            'fixture_preview': fixture_preview,
            'data_quality': xgi_stats.get('data_quality', 'unknown'),
        }
    
    print(f"Matched {matched_count}/{len(players)} players with Understat data")
    
    # Get user's team
    print("Fetching your team...")
    my_team_data = fetch_json(PICKS_URL.format(gw=current_gw))
    my_entry = fetch_json(TEAM_URL)
    my_history = fetch_json(HISTORY_URL)
    
    transfers = []
    captains = []
    chip_strategy = []
    starting_xi_recs = []
    my_team_output = None
    my_picks = []
    
    if my_team_data and my_entry:
        my_picks = my_team_data.get('picks', [])

        # Fetch rolling form for user's squad (v4.0 quick win)
        print("Fetching rolling form for your squad...")
        for pick in my_picks:
            player_id = pick['element']
            p = next((pl for pl in players if pl['id'] == player_id), {})
            pick['element_type'] = p.get('element_type', 0)
            pick['web_name'] = p.get('web_name', 'Unknown')
            pick['selling_price'] = pick.get('selling_price', p.get('now_cost', 0))
            pick['team_id'] = p.get('team', 0)

            # Get detailed history and calculate rolling form
            history_data = get_player_history(player_id)
            if history_data and 'history' in history_data:
                rolling = calculate_rolling_form(history_data['history'], matches=5)
                # Update projection with rolling form data
                if player_id in projections:
                    projections[player_id]['rolling_form'] = rolling['rolling_form']
                    projections[player_id]['rolling_xgi'] = rolling.get('rolling_xgi', 0)
                    projections[player_id]['form_direction'] = rolling['trend']
        
        bank = my_entry.get('last_deadline_bank', 0) / 10
        
        chips_available = {'bench_boost', 'triple_captain', 'free_hit', 'wildcard'}
        if my_history and 'chips' in my_history:
            for chip in my_history['chips']:
                chip_name = chip.get('name', '').lower().replace(' ', '_')
                if chip_name in chips_available:
                    chips_available.discard(chip_name)
        
        print(f"Chips available: {chips_available}")
        
        transfers = get_transfer_recommendations(
            my_picks, players, projections, bank,
            fixture_data, team_strengths, next_gw
        )
        
        captains = get_captain_picks(my_picks, projections, players, fixture_data, current_gw)
        
        chip_strategy = analyze_chip_strategy(
            my_picks, projections, fixture_data, team_strengths,
            next_gw, chips_available
        )
        
        # Generate Starting XI recommendations (NEW)
        print("Generating Starting XI recommendations...")
        starting_xi_recs = generate_starting_xi_recommendations(
            my_picks, players, projections,
            fixture_data, team_strengths, next_gw
        )
        
        my_team_output = {
            'team_id': TEAM_ID,
            'current_gw': current_gw,
            'next_gw': next_gw,
            'bank': round(bank, 1),
            'chips_available': list(chips_available),
            'squad': [{
                'player_id': p['element'],
                'name': p['web_name'],
                'position': p['element_type'],
                'team_id': p['team_id'],
                'is_captain': p['is_captain'],
                'is_vice': p['is_vice_captain'],
                'multiplier': p['multiplier'],
                'selling_price': p['selling_price'] / 10,
                'projected_pts': projections.get(p['element'], {}).get('next_gw_pts', 0),
                'projected_4gw': projections.get(p['element'], {}).get('next_4gw_pts', 0),
                'form_trend': projections.get(p['element'], {}).get('form_trend', 'neutral'),
                'rolling_form': projections.get(p['element'], {}).get('rolling_form'),
                'form_direction': projections.get(p['element'], {}).get('form_direction'),
                'news': projections.get(p['element'], {}).get('news', ''),
                'news_severity': projections.get(p['element'], {}).get('news_severity', 0),
                'news_category': projections.get(p['element'], {}).get('news_category', 'healthy'),
                'fixture_preview': projections.get(p['element'], {}).get('fixture_preview', [])[:4],
            } for p in my_picks],
            'total_projected_pts': round(sum(
                projections.get(p['element'], {}).get('next_gw_pts', 0) * p['multiplier']
                for p in my_picks if p['multiplier'] > 0
            ), 1),
        }
    
    # Build outputs
    recommendations = {
        'generated_at': datetime.utcnow().isoformat(),
        'next_gameweek': next_gw,
        'data_source': f"Understat ({matched_count} players matched)",
        'captain_picks': captains,
        'transfer_recommendations': transfers,
        'chip_strategy': chip_strategy,
        'fixture_alerts': {
            'dgw_gws': fixture_data['dgw_gws'],
            'bgw_gws': fixture_data['bgw_gws'],
        },
    }
    
    top_by_position = {}
    for pos, name in [(1, 'GK'), (2, 'DEF'), (3, 'MID'), (4, 'FWD')]:
        pos_players = [p for p in projections.values() if p['position'] == pos]
        pos_players.sort(key=lambda x: x['next_4gw_pts'], reverse=True)
        top_by_position[name] = pos_players[:15]
    
    # Save outputs
    output_dir = Path('public/data')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'projections.json', 'w') as f:
        json.dump({
            'generated_at': datetime.utcnow().isoformat(),
            'next_gameweek': next_gw,
            'top_by_position': top_by_position,
        }, f, indent=2)
    
    with open(output_dir / 'recommendations.json', 'w') as f:
        json.dump(recommendations, f, indent=2)
    
    if my_team_output:
        with open(output_dir / 'my_team.json', 'w') as f:
            json.dump(my_team_output, f, indent=2)
    
    # Save Starting XI recommendations (NEW)
    if starting_xi_recs:
        with open(output_dir / 'starting_xi.json', 'w') as f:
            json.dump({
                'generated_at': datetime.utcnow().isoformat(),
                'team_id': TEAM_ID,
                'next_gameweek': next_gw,
                'recommendations': starting_xi_recs,
            }, f, indent=2)
    
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print('=' * 60)
    print(f"Files written to {output_dir}/")
    
    if captains and captains.get('picks'):
        c = captains['safe_pick']
        dgw_flag = " 🎯 DGW!" if c.get('has_dgw') else ""
        print(f"\n👑 Safe Captain: {c['name']} ({c['projected_pts']:.1f} pts, {c['ownership']:.1f}% EO){dgw_flag}")
        diff = captains.get('differential_pick')
        if diff and diff['name'] != c['name']:
            print(f"   🎯 Differential: {diff['name']} ({diff['projected_pts']:.1f} pts, {diff['ownership']:.1f}% owned)")
            print(f"      → {diff['vs_safe_diff']:+.1f} pts vs safe, {diff['eo_advantage']:.0f}% EO advantage")
    
    if transfers:
        print(f"\n📈 Transfer Recommendations:")
        for t in transfers[:2]:
            reasons = ', '.join(t['buy_reasons']) if t['buy_reasons'] else 'better projection'
            print(f"   {t['out_name']} → {t['in_name']} (+{t['gain_4gw']} pts/4GW) [{reasons}]")
    
    if chip_strategy:
        print(f"\n🎮 Chip Strategy:")
        for chip in chip_strategy:
            print(f"   {chip['chip']}: GW{chip['recommended_gw']} ({chip['confidence']})")
    
    # Print Starting XI summary (NEW)
    if starting_xi_recs:
        xi = starting_xi_recs[0]
        print(f"\n📋 GW{xi['gameweek']} Starting XI ({xi['formation']}):")
        print(f"   Captain: {xi['captain']['name']} ({xi['captain']['effective_pts']} eff pts)")
        print(f"   Total effective: {xi['total_effective_pts']} pts")
    
    print("\nDone!")


if __name__ == '__main__':
    run_projections()
