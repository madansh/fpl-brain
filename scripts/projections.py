"""
FPL Brain - Projection Engine v3.1
- Real xG from Understat
- Smarter transfer logic with form, fixtures, DGW awareness
- Chip strategy optimizer (BB/TC/FH/WC timing)
- xMin calculation + Starting XI recommendations (NEW)
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


def match_player_names(fpl_name, fpl_team, understat_players, team_mapping):
    fpl_name_clean = fpl_name.lower().strip()
    best_match = None
    best_score = 0
    
    for us_player in understat_players:
        us_name = us_player.get('player_name', '').lower()
        us_team = us_player.get('team_name', '')
        
        fpl_team_name = team_mapping.get(fpl_team, '').lower()
        if fpl_team_name and fpl_team_name not in us_team.lower():
            continue
        
        score = SequenceMatcher(None, fpl_name_clean, us_name).ratio()
        if fpl_name_clean in us_name or us_name.split()[-1] == fpl_name_clean:
            score = max(score, 0.85)
        
        if score > best_score and score > 0.6:
            best_score = score
            best_match = us_player
    
    return best_match


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
        if proj_4gw < 12:
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
            
            proj_4gw = proj.get('next_4gw_pts', 0)
            gain_4gw = proj_4gw - weak['proj_4gw']
            
            if gain_4gw < 1:
                continue
            
            buy_score = gain_4gw
            buy_reasons = []
            
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
# CHIP STRATEGY OPTIMIZER
# =============================================================================

def analyze_chip_strategy(my_squad, projections, fixture_data, team_strengths, 
                          current_gw, chips_available):
    recommendations = []
    
    dgw_gws = fixture_data['dgw_gws']
    bgw_gws = fixture_data['bgw_gws']
    team_dgws = fixture_data['team_dgws']
    team_bgws = fixture_data['team_bgws']
    
    # BENCH BOOST
    if 'bench_boost' in chips_available:
        best_bb_gw = None
        best_bb_score = 0
        bb_analysis = []
        
        for gw in dgw_gws:
            if gw < current_gw:
                continue
            
            dgw_players = 0
            bench_dgw_players = 0
            total_bench_proj = 0
            
            for pick in my_squad:
                team_id = pick.get('team_id', 0)
                is_bench = pick.get('multiplier', 0) == 0
                player_proj = projections.get(pick['element'], {})
                
                has_dgw = gw in team_dgws.get(team_id, [])
                
                if has_dgw:
                    dgw_players += 1
                    if is_bench:
                        bench_dgw_players += 1
                        base_pts = player_proj.get('next_gw_pts', 2)
                        total_bench_proj += base_pts * 1.8
                elif is_bench:
                    total_bench_proj += player_proj.get('next_gw_pts', 2)
            
            bb_score = total_bench_proj + (dgw_players * 2)
            
            bb_analysis.append({
                'gw': gw,
                'dgw_players': dgw_players,
                'bench_dgw': bench_dgw_players,
                'bench_proj': round(total_bench_proj, 1),
                'score': round(bb_score, 1),
            })
            
            if bb_score > best_bb_score:
                best_bb_score = bb_score
                best_bb_gw = gw
        
        if best_bb_gw:
            best_analysis = next(a for a in bb_analysis if a['gw'] == best_bb_gw)
            recommendations.append({
                'chip': 'Bench Boost',
                'recommended_gw': best_bb_gw,
                'confidence': 'HIGH' if best_analysis['dgw_players'] >= 10 else 'MEDIUM',
                'reasoning': f"GW{best_bb_gw} is a DGW with {best_analysis['dgw_players']} of your players doubling. Projected bench value: {best_analysis['bench_proj']} pts.",
                'action_needed': f"Ensure bench has playing DGW players by GW{best_bb_gw}.",
                'analysis': bb_analysis,
            })
    
    # TRIPLE CAPTAIN
    if 'triple_captain' in chips_available:
        best_tc_gw = None
        best_tc_player = None
        best_tc_score = 0
        tc_analysis = []
        
        premiums = [p for p in my_squad if p.get('selling_price', 0) / 10 >= 10]
        
        for gw in dgw_gws:
            if gw < current_gw:
                continue
            
            for pick in premiums:
                team_id = pick.get('team_id', 0)
                player_id = pick['element']
                
                if gw not in team_dgws.get(team_id, []):
                    continue
                
                proj = projections.get(player_id, {})
                player_name = pick.get('web_name', 'Unknown')
                
                gw_fixtures = fixture_data['team_fixtures'].get(team_id, {}).get(gw, [])
                
                total_diff = 0
                fixture_strs = []
                for fix in gw_fixtures:
                    diff = get_fixture_difficulty(team_strengths, fix['opponent_id'], fix['is_home'])
                    total_diff += diff
                    h_a = '(H)' if fix['is_home'] else '(A)'
                    fixture_strs.append(f"{fix['opponent']} {h_a}")
                
                avg_diff = total_diff / len(gw_fixtures) if gw_fixtures else 1.0
                
                base_pts = proj.get('next_gw_pts', 4)
                tc_score = (base_pts * 2 / avg_diff) * 3
                
                tc_analysis.append({
                    'gw': gw,
                    'player': player_name,
                    'player_id': player_id,
                    'fixtures': fixture_strs,
                    'avg_difficulty': round(avg_diff, 2),
                    'projected_tc_pts': round(tc_score, 1),
                })
                
                if tc_score > best_tc_score:
                    best_tc_score = tc_score
                    best_tc_gw = gw
                    best_tc_player = player_name
        
        if best_tc_gw:
            best = next(a for a in tc_analysis if a['gw'] == best_tc_gw and a['player'] == best_tc_player)
            recommendations.append({
                'chip': 'Triple Captain',
                'recommended_gw': best_tc_gw,
                'recommended_player': best_tc_player,
                'confidence': 'HIGH' if best['avg_difficulty'] < 0.95 else 'MEDIUM',
                'reasoning': f"TC {best_tc_player} in GW{best_tc_gw} ({', '.join(best['fixtures'])}). Projected: {best['projected_tc_pts']} pts.",
                'action_needed': f"Ensure {best_tc_player} is in your squad for GW{best_tc_gw}.",
                'analysis': sorted(tc_analysis, key=lambda x: -x['projected_tc_pts'])[:5],
            })
    
    # FREE HIT
    if 'free_hit' in chips_available:
        best_fh_gw = None
        worst_coverage = 15
        fh_analysis = []
        
        for gw in bgw_gws:
            if gw < current_gw:
                continue
            
            players_with_fixtures = 0
            players_blanking = []
            
            for pick in my_squad:
                team_id = pick.get('team_id', 0)
                gw_fixtures = fixture_data['team_fixtures'].get(team_id, {}).get(gw, [])
                
                if gw_fixtures:
                    players_with_fixtures += 1
                else:
                    players_blanking.append(pick.get('web_name', 'Unknown'))
            
            fh_analysis.append({
                'gw': gw,
                'players_with_fixtures': players_with_fixtures,
                'players_blanking': len(players_blanking),
                'blanking_names': players_blanking[:5],
            })
            
            if players_with_fixtures < worst_coverage:
                worst_coverage = players_with_fixtures
                best_fh_gw = gw
        
        if best_fh_gw and worst_coverage < 9:
            best = next(a for a in fh_analysis if a['gw'] == best_fh_gw)
            recommendations.append({
                'chip': 'Free Hit',
                'recommended_gw': best_fh_gw,
                'confidence': 'HIGH' if worst_coverage < 7 else 'MEDIUM',
                'reasoning': f"GW{best_fh_gw} is a BGW where only {worst_coverage} of your players have fixtures.",
                'action_needed': f"Save Free Hit for GW{best_fh_gw}. Don't waste transfers preparing.",
                'players_blanking': best['blanking_names'],
                'analysis': fh_analysis,
            })
    
    # WILDCARD
    if 'wildcard' in chips_available:
        wc_triggers = []
        wc_score = 0
        
        for pick in my_squad:
            proj = projections.get(pick['element'], {})
            if proj.get('form_trend') == 'cold':
                wc_score += 1
                wc_triggers.append('cold_player')
        
        dgw_coverage = 0
        for pick in my_squad:
            team_id = pick.get('team_id', 0)
            if any(gw in team_dgws.get(team_id, []) for gw in dgw_gws if gw > current_gw):
                dgw_coverage += 1
        
        if dgw_coverage < 8 and dgw_gws:
            wc_score += 3
            wc_triggers.append('poor_dgw_coverage')
        
        injured = sum(1 for p in my_squad 
                     if projections.get(p['element'], {}).get('chance_of_playing') is not None
                     and projections.get(p['element'], {}).get('chance_of_playing') < 75)
        if injured >= 3:
            wc_score += 2
            wc_triggers.append(f'{injured}_injuries')
        
        if wc_score >= 3:
            best_wc_gw = current_gw + 1
            if dgw_gws:
                best_wc_gw = min(dgw_gws) - 1 if min(dgw_gws) > current_gw else current_gw + 1
            
            recommendations.append({
                'chip': 'Wildcard',
                'recommended_gw': best_wc_gw,
                'confidence': 'HIGH' if wc_score >= 5 else 'MEDIUM',
                'reasoning': f"Consider WC in GW{best_wc_gw} to fix squad issues: {', '.join(set(wc_triggers))}",
                'action_needed': "Restructure squad for upcoming DGWs and fixture swings.",
                'triggers': wc_triggers,
            })
    
    return recommendations


# =============================================================================
# CAPTAIN SELECTION
# =============================================================================

def get_captain_picks(my_squad, projections, all_players, fixture_data, current_gw):
    captain_options = []
    player_lookup = {p['id']: p for p in all_players}
    
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
            
            captain_options.append({
                'player_id': player_id,
                'name': player.get('web_name', 'Unknown'),
                'team': proj.get('team', '?'),
                'projected_pts': proj_pts,
                'doubled_pts': round(proj_pts * 2, 1),
                'fixture': proj.get('next_fixture', ''),
                'fixture_difficulty': proj.get('next_fixture_diff', 1.0),
                'ownership': ownership,
                'form': player.get('form', '0'),
                'form_trend': proj.get('form_trend', 'neutral'),
                'is_differential': ownership < 15,
                'has_dgw': has_dgw,
                'data_quality': proj.get('data_quality', 'unknown'),
            })
    
    captain_options.sort(key=lambda x: (-x['has_dgw'], -x['projected_pts']))
    return captain_options[:5]


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_projections():
    print("=" * 60)
    print("FPL BRAIN v3.1 - Projection Engine")
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
                player['web_name'], team_id, understat_players, team_name_map
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
        
        for pick in my_picks:
            p = next((pl for pl in players if pl['id'] == pick['element']), {})
            pick['element_type'] = p.get('element_type', 0)
            pick['web_name'] = p.get('web_name', 'Unknown')
            pick['selling_price'] = pick.get('selling_price', p.get('now_cost', 0))
            pick['team_id'] = p.get('team', 0)
        
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
    
    if captains:
        c = captains[0]
        dgw_flag = " 🎯 DGW!" if c.get('has_dgw') else ""
        print(f"\n👑 Top Captain: {c['name']} ({c['projected_pts']:.1f} pts){dgw_flag}")
    
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
