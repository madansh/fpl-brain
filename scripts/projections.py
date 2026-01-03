"""
FPL Brain - Projection Engine
Generates xG-based recommendations for captain, transfers, and chip timing.
"""

import requests
import json
from datetime import datetime, timedelta
from pathlib import Path
import math

# =============================================================================
# CONFIGURATION
# =============================================================================

TEAM_ID = 5033680
PLANNING_HORIZON = 4  # Gameweeks to optimize transfers over
HIT_THRESHOLD_GWS = 3  # Take hit if gain > 4 over this many GWs (aggressive)
FORM_WEIGHT = 0.6  # 60% recent form, 40% season average
DECAY_FACTOR = 0.85  # Each older match weighted 15% less

# FPL API endpoints
BASE_URL = "https://fantasy.premierleague.com/api"
BOOTSTRAP_URL = f"{BASE_URL}/bootstrap-static/"
FIXTURES_URL = f"{BASE_URL}/fixtures/"
TEAM_URL = f"{BASE_URL}/entry/{TEAM_ID}/"
PICKS_URL = f"{BASE_URL}/entry/{TEAM_ID}/event/{{gw}}/picks/"
PLAYER_URL = f"{BASE_URL}/element-summary/{{player_id}}/"

# Points mapping
PTS_GOAL = {1: 6, 2: 6, 3: 5, 4: 4}  # GK, DEF, MID, FWD
PTS_ASSIST = 3
PTS_CLEAN_SHEET = {1: 4, 2: 4, 3: 1, 4: 0}
PTS_APPEARANCE = 2
PTS_BONUS_AVG = 1.2  # Average bonus for high xGI players


# =============================================================================
# DATA FETCHING
# =============================================================================

def fetch_json(url):
    """Fetch JSON from URL with error handling."""
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None


def get_bootstrap_data():
    """Get all static FPL data - players, teams, gameweeks."""
    return fetch_json(BOOTSTRAP_URL)


def get_fixtures():
    """Get all fixtures for the season."""
    return fetch_json(FIXTURES_URL)


def get_my_team(current_gw):
    """Get user's current squad."""
    url = PICKS_URL.format(gw=current_gw)
    return fetch_json(url)


def get_player_history(player_id):
    """Get detailed player history including past fixtures."""
    url = PLAYER_URL.format(player_id=player_id)
    return fetch_json(url)


# =============================================================================
# TEAM STRENGTH CALCULATION
# =============================================================================

def calculate_team_strengths(teams, fixtures):
    """
    Calculate defensive/offensive strength per team based on season performance.
    Returns xG conceded and xG scored estimates.
    """
    # FPL provides strength ratings - we'll enhance with fixture results
    team_strength = {}
   
    for team in teams:
        team_strength[team['id']] = {
            'name': team['name'],
            'short_name': team['short_name'],
            'strength_attack_home': team['strength_attack_home'],
            'strength_attack_away': team['strength_attack_away'],
            'strength_defence_home': team['strength_defence_home'],
            'strength_defence_away': team['strength_defence_away'],
            # Derive clean sheet probability from defensive strength
            # Higher defensive strength = higher CS probability
            'cs_prob_home': min(0.45, team['strength_defence_home'] / 3000),
            'cs_prob_away': min(0.35, team['strength_defence_away'] / 3200),
        }
   
    return team_strength


def get_fixture_difficulty(team_strengths, opponent_id, is_home):
    """
    Return a difficulty multiplier (0.7 - 1.3) based on opponent.
    Lower = easier fixture = higher expected points.
    """
    opp = team_strengths.get(opponent_id, {})
   
    if is_home:
        # Playing at home against opponent's away attack
        opp_attack = opp.get('strength_attack_away', 1100)
    else:
        # Playing away against opponent's home attack
        opp_attack = opp.get('strength_attack_home', 1200)
   
    # Normalize: 1000 = easy (0.8), 1200 = average (1.0), 1400 = hard (1.2)
    difficulty = 0.8 + (opp_attack - 1000) / 1000
    return max(0.7, min(1.3, difficulty))


# =============================================================================
# FORM & PROJECTION CALCULATIONS
# =============================================================================

def calculate_form_xgi(player_history, num_matches=5):
    """
    Calculate form-weighted xGI from recent matches.
    Uses exponential decay - recent matches count more.
   
    Since FPL API doesn't give raw xG, we estimate from:
    - Goals scored (reverse engineer approximate xG)
    - Assists
    - Expected bonus points
    """
    if not player_history or 'history' not in player_history:
        return None
   
    history = player_history['history']
    if not history:
        return None
   
    # Get last N matches where player had minutes
    recent = [h for h in history if h['minutes'] > 0][-num_matches:]
   
    if not recent:
        return None
   
    weighted_goals = 0
    weighted_assists = 0
    weighted_minutes = 0
    total_weight = 0
   
    for i, match in enumerate(reversed(recent)):  # Most recent first
        weight = DECAY_FACTOR ** i
       
        # Per 90 normalization
        mins = match['minutes']
        if mins > 0:
            goals_p90 = (match['goals_scored'] / mins) * 90
            assists_p90 = (match['assists'] / mins) * 90
           
            weighted_goals += goals_p90 * weight
            weighted_assists += assists_p90 * weight
            weighted_minutes += mins * weight
            total_weight += weight
   
    if total_weight == 0:
        return None
   
    return {
        'goals_p90': weighted_goals / total_weight,
        'assists_p90': weighted_assists / total_weight,
        'avg_minutes': weighted_minutes / total_weight,
        'matches_played': len(recent)
    }


def calculate_season_xgi(player):
    """Calculate season average xGI from bootstrap data."""
    mins = player.get('minutes', 0)
    if mins < 90:  # Not enough data
        return None
   
    goals = player.get('goals_scored', 0)
    assists = player.get('assists', 0)
   
    return {
        'goals_p90': (goals / mins) * 90,
        'assists_p90': (assists / mins) * 90,
        'avg_minutes': mins / max(1, player.get('starts', 1)),
    }


def blend_projections(form_xgi, season_xgi):
    """Blend form and season stats with configured weighting."""
    if form_xgi is None and season_xgi is None:
        return None
   
    if form_xgi is None:
        return season_xgi
   
    if season_xgi is None:
        return form_xgi
   
    return {
        'goals_p90': (form_xgi['goals_p90'] * FORM_WEIGHT +
                      season_xgi['goals_p90'] * (1 - FORM_WEIGHT)),
        'assists_p90': (form_xgi['assists_p90'] * FORM_WEIGHT +
                        season_xgi['assists_p90'] * (1 - FORM_WEIGHT)),
        'avg_minutes': (form_xgi['avg_minutes'] * FORM_WEIGHT +
                        season_xgi['avg_minutes'] * (1 - FORM_WEIGHT)),
    }


def project_gameweek_points(player, projection, fixture_difficulty,
                            team_cs_prob, element_type):
    """
    Project points for a single gameweek.
   
    Points = (xG × goal_pts) + (xA × 3) + (CS_prob × CS_pts) + appearance + bonus
    """
    if projection is None:
        return 0
   
    # Availability check
    chance = player.get('chance_of_playing_next_round')
    if chance is not None and chance < 50:
        return 0
   
    availability_mult = (chance / 100) if chance is not None else 0.95
   
    # Minutes probability (will they play 60+?)
    mins_prob = min(1.0, projection['avg_minutes'] / 70)
   
    # Expected goals and assists, adjusted for fixture
    xg = projection['goals_p90'] / fixture_difficulty
    xa = projection['assists_p90'] / fixture_difficulty
   
    # Points calculation
    goal_pts = xg * PTS_GOAL.get(element_type, 4)
    assist_pts = xa * PTS_ASSIST
   
    # Clean sheet (defenders and GKs)
    cs_pts = team_cs_prob * PTS_CLEAN_SHEET.get(element_type, 0) / fixture_difficulty
   
    # Appearance points (assume they play if mins_prob > 0.5)
    appearance_pts = PTS_APPEARANCE if mins_prob > 0.5 else 1
   
    # Bonus estimate (correlated with xGI)
    xgi = xg + xa
    bonus_pts = min(3, xgi * 2) if xgi > 0.3 else 0
   
    total = (goal_pts + assist_pts + cs_pts + appearance_pts + bonus_pts)
   
    return round(total * availability_mult * mins_prob, 2)


# =============================================================================
# TRANSFER LOGIC
# =============================================================================

def get_best_transfers(my_squad, all_players, projections, bank, free_transfers):
    """
    Find optimal transfers considering:
    - 4 GW planning horizon
    - Price constraints
    - Position limits
    - Hit threshold for aggressive play
    """
    recommendations = []
   
    # Group players by position
    by_position = {1: [], 2: [], 3: [], 4: []}
    for p in all_players:
        pos = p['element_type']
        player_proj = projections.get(p['id'], {})
        if player_proj:
            by_position[pos].append({
                'player': p,
                'projected_4gw': player_proj.get('next_4gw_pts', 0),
                'projected_1gw': player_proj.get('next_gw_pts', 0),
            })
   
    # Sort each position by 4GW projection
    for pos in by_position:
        by_position[pos].sort(key=lambda x: x['projected_4gw'], reverse=True)
   
    # Find weakest players in squad
    squad_with_proj = []
    for pick in my_squad:
        player_id = pick['element']
        proj = projections.get(player_id, {})
        squad_with_proj.append({
            'player_id': player_id,
            'position': pick['element_type'],
            'selling_price': pick.get('selling_price', 0),
            'projected_4gw': proj.get('next_4gw_pts', 0),
            'projected_1gw': proj.get('next_gw_pts', 0),
        })
   
    # Sort by projected points (lowest first = transfer out candidates)
    squad_with_proj.sort(key=lambda x: x['projected_4gw'])
   
    # For each weak player, find best replacement within budget
    for weak in squad_with_proj[:3]:  # Check bottom 3
        pos = weak['position']
        budget = bank + weak['selling_price']
       
        for candidate in by_position[pos][:10]:
            cand_player = candidate['player']
           
            # Skip if already in squad
            if cand_player['id'] in [p['player_id'] for p in squad_with_proj]:
                continue
           
            # Check budget
            if cand_player['now_cost'] > budget:
                continue
           
            # Calculate gain
            gain_4gw = candidate['projected_4gw'] - weak['projected_4gw']
            gain_1gw = candidate['projected_1gw'] - weak['projected_1gw']
           
            # Worth a hit? (aggressive: gain > 4 over 3 GWs)
            worth_hit = gain_4gw > (4 * (4 / HIT_THRESHOLD_GWS))
           
            if gain_4gw > 2:  # Meaningful improvement
                recommendations.append({
                    'out_id': weak['player_id'],
                    'in_id': cand_player['id'],
                    'in_name': cand_player['web_name'],
                    'in_team': cand_player['team'],
                    'in_cost': cand_player['now_cost'] / 10,
                    'gain_4gw': round(gain_4gw, 1),
                    'gain_1gw': round(gain_1gw, 1),
                    'worth_hit': worth_hit,
                    'position': pos,
                })
                break  # One rec per weak player
   
    # Sort by 4GW gain
    recommendations.sort(key=lambda x: x['gain_4gw'], reverse=True)
   
    return recommendations


# =============================================================================
# CAPTAIN SELECTION
# =============================================================================

def get_captain_picks(my_squad, projections, all_players, ownership_data):
    """
    Rank captain options by projected points.
    Include ownership for differential consideration.
    """
    captain_options = []
   
    player_lookup = {p['id']: p for p in all_players}
   
    for pick in my_squad:
        player_id = pick['element']
        proj = projections.get(player_id, {})
        player = player_lookup.get(player_id, {})
       
        if proj.get('next_gw_pts', 0) > 2:
            captain_options.append({
                'player_id': player_id,
                'name': player.get('web_name', 'Unknown'),
                'team': player.get('team', 0),
                'projected_pts': proj.get('next_gw_pts', 0),
                'fixture': proj.get('next_fixture', ''),
                'fixture_difficulty': proj.get('next_fixture_diff', 3),
                'ownership': player.get('selected_by_percent', '0'),
                'form': player.get('form', '0'),
            })
   
    # Sort by projected points
    captain_options.sort(key=lambda x: x['projected_pts'], reverse=True)
   
    return captain_options[:5]


# =============================================================================
# CHIP PLANNING
# =============================================================================

def analyze_chip_timing(fixtures, current_gw, chips_remaining):
    """
    Analyze upcoming fixtures to recommend chip timing.
   
    - Bench Boost: Double gameweek with strong bench
    - Triple Captain: Premium player with double + easy fixtures
    - Free Hit: Blank gameweek
    - Wildcard: Major squad restructure needed
    """
    recommendations = []
   
    # Look for double and blank gameweeks
    gw_fixture_counts = {}
    for f in fixtures:
        gw = f.get('event')
        if gw and gw >= current_gw:
            gw_fixture_counts[gw] = gw_fixture_counts.get(gw, 0) + 1
   
    # Standard is 10 fixtures per GW (20 teams / 2)
    for gw, count in gw_fixture_counts.items():
        if gw > current_gw + 10:  # Only look 10 weeks ahead
            continue
           
        if count > 10:  # Double gameweek
            recommendations.append({
                'gameweek': gw,
                'type': 'double',
                'fixtures': count,
                'chip_suggestion': 'Bench Boost or Triple Captain',
                'notes': f'GW{gw} has {count} fixtures - plan transfers to maximize DGW players'
            })
        elif count < 10:  # Blank gameweek
            recommendations.append({
                'gameweek': gw,
                'type': 'blank',
                'fixtures': count,
                'chip_suggestion': 'Free Hit candidate',
                'notes': f'GW{gw} has only {count} fixtures - consider Free Hit if squad coverage is poor'
            })
   
    return recommendations


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_projections():
    """Main function to generate all projections and recommendations."""
   
    print("Fetching FPL data...")
    bootstrap = get_bootstrap_data()
    fixtures = get_fixtures()
   
    if not bootstrap or not fixtures:
        print("Failed to fetch data")
        return
   
    players = bootstrap['elements']
    teams = bootstrap['teams']
    events = bootstrap['events']
   
    # Find current gameweek
    current_gw = next((e['id'] for e in events if e['is_current']), 1)
    next_gw = current_gw + 1 if not any(e['is_next'] for e in events) else \
              next(e['id'] for e in events if e['is_next'])
   
    print(f"Current GW: {current_gw}, Next GW: {next_gw}")
   
    # Get team strengths
    team_strengths = calculate_team_strengths(teams, fixtures)
    team_lookup = {t['id']: t for t in teams}
   
    # Get upcoming fixtures per team
    upcoming = {}
    for f in fixtures:
        if f['event'] and f['event'] >= next_gw and f['event'] < next_gw + 6:
            for team_id, is_home in [(f['team_h'], True), (f['team_a'], False)]:
                if team_id not in upcoming:
                    upcoming[team_id] = []
                opp_id = f['team_a'] if is_home else f['team_h']
                upcoming[team_id].append({
                    'gw': f['event'],
                    'opponent': opp_id,
                    'is_home': is_home,
                    'difficulty': get_fixture_difficulty(team_strengths, opp_id, is_home)
                })
   
    # Calculate projections for all players
    print("Calculating projections...")
    projections = {}
   
    for player in players:
        player_id = player['id']
        team_id = player['team']
        element_type = player['element_type']
       
        # Get form and season stats
        season_xgi = calculate_season_xgi(player)
       
        # For now, use season stats (form would require individual API calls)
        # In production, we'd batch these or use cached data
        projection = season_xgi
       
        if projection is None:
            continue
       
        # Get team's upcoming fixtures
        team_fixtures = upcoming.get(team_id, [])
       
        # Project points for next 6 gameweeks
        gw_projections = []
        for i, fix in enumerate(team_fixtures[:6]):
            cs_prob = team_strengths.get(team_id, {}).get(
                'cs_prob_home' if fix['is_home'] else 'cs_prob_away', 0.2
            )
            pts = project_gameweek_points(
                player, projection, fix['difficulty'], cs_prob, element_type
            )
            gw_projections.append({
                'gw': fix['gw'],
                'projected_pts': pts,
                'opponent': team_lookup.get(fix['opponent'], {}).get('short_name', '?'),
                'is_home': fix['is_home'],
                'difficulty': fix['difficulty']
            })
       
        # Store projections
        next_fix = gw_projections[0] if gw_projections else {}
        projections[player_id] = {
            'player_id': player_id,
            'name': player['web_name'],
            'team': team_lookup.get(team_id, {}).get('short_name', '?'),
            'position': element_type,
            'price': player['now_cost'] / 10,
            'ownership': player['selected_by_percent'],
            'form': player['form'],
            'news': player.get('news', ''),
            'chance_of_playing': player.get('chance_of_playing_next_round'),
            'next_gw_pts': next_fix.get('projected_pts', 0),
            'next_fixture': f"{'(H)' if next_fix.get('is_home') else '(A)'} {next_fix.get('opponent', '?')}",
            'next_fixture_diff': next_fix.get('difficulty', 1),
            'next_4gw_pts': sum(g['projected_pts'] for g in gw_projections[:4]),
            'next_6gw_pts': sum(g['projected_pts'] for g in gw_projections[:6]),
            'fixtures': gw_projections,
        }
   
    # Get my team
    print("Fetching your team...")
    my_team_data = get_my_team(current_gw)
    my_entry = fetch_json(TEAM_URL)
   
    if my_team_data and my_entry:
        my_picks = my_team_data.get('picks', [])
       
        # Enrich picks with player data
        for pick in my_picks:
            player = next((p for p in players if p['id'] == pick['element']), {})
            pick['element_type'] = player.get('element_type', 0)
            pick['web_name'] = player.get('web_name', 'Unknown')
            pick['selling_price'] = pick.get('selling_price', player.get('now_cost', 0))
       
        bank = my_entry.get('last_deadline_bank', 0) / 10
       
        # Get transfer recommendations
        transfers = get_best_transfers(
            my_picks, players, projections, bank,
            my_team_data.get('transfers', {}).get('limit', 1)
        )
       
        # Get captain picks
        captains = get_captain_picks(my_picks, projections, players, {})
       
        # Analyze chip timing
        chips_used = []  # Would parse from entry history
        chip_analysis = analyze_chip_timing(fixtures, next_gw, chips_used)
       
        # Build my team output
        my_team_output = {
            'team_id': TEAM_ID,
            'current_gw': current_gw,
            'next_gw': next_gw,
            'bank': bank,
            'squad': [{
                'player_id': p['element'],
                'name': p['web_name'],
                'position': p['element_type'],
                'is_captain': p['is_captain'],
                'is_vice': p['is_vice_captain'],
                'multiplier': p['multiplier'],
                'projected_pts': projections.get(p['element'], {}).get('next_gw_pts', 0),
                'projected_4gw': projections.get(p['element'], {}).get('next_4gw_pts', 0),
            } for p in my_picks],
            'total_projected_pts': sum(
                projections.get(p['element'], {}).get('next_gw_pts', 0) * p['multiplier']
                for p in my_picks if p['multiplier'] > 0
            ),
        }
    else:
        my_team_output = None
        transfers = []
        captains = []
        chip_analysis = analyze_chip_timing(fixtures, next_gw, [])
   
    # Build recommendations output
    recommendations = {
        'generated_at': datetime.utcnow().isoformat(),
        'next_gameweek': next_gw,
        'captain_picks': captains,
        'transfer_recommendations': transfers,
        'chip_analysis': chip_analysis,
    }
   
    # Build top players by position for general browsing
    top_by_position = {}
    for pos, pos_name in [(1, 'GK'), (2, 'DEF'), (3, 'MID'), (4, 'FWD')]:
        pos_players = [p for p in projections.values() if p['position'] == pos]
        pos_players.sort(key=lambda x: x['next_4gw_pts'], reverse=True)
        top_by_position[pos_name] = pos_players[:15]
   
    # Save outputs
    output_dir = Path('data')
    output_dir.mkdir(exist_ok=True)
   
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
   
    print(f"Done! Files written to {output_dir}/")
    print(f"Top captain pick: {captains[0]['name'] if captains else 'N/A'}")
    if transfers:
        print(f"Top transfer: {transfers[0]['in_name']} (gain: {transfers[0]['gain_4gw']} pts over 4GW)")


if __name__ == '__main__':
    run_projections()
