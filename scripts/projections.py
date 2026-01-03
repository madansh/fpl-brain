"""
FPL Brain - Projection Engine v2
Now with REAL xG data from Understat + improved fixture difficulty
"""

import requests
import json
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
from understatapi import UnderstatClient

# =============================================================================
# CONFIGURATION
# =============================================================================

TEAM_ID = 5033680
PLANNING_HORIZON = 4
HIT_THRESHOLD_GWS = 3  # Aggressive: take hit if gain > 4 over 3 GWs
FORM_WEIGHT = 0.6  # 60% recent form, 40% season average
DECAY_FACTOR = 0.85

# FPL API endpoints
BASE_URL = "https://fantasy.premierleague.com/api"
BOOTSTRAP_URL = f"{BASE_URL}/bootstrap-static/"
FIXTURES_URL = f"{BASE_URL}/fixtures/"
TEAM_URL = f"{BASE_URL}/entry/{TEAM_ID}/"
PICKS_URL = f"{BASE_URL}/entry/{TEAM_ID}/event/{{gw}}/picks/"

# Points mapping
PTS_GOAL = {1: 6, 2: 6, 3: 5, 4: 4}
PTS_ASSIST = 3
PTS_CLEAN_SHEET = {1: 4, 2: 4, 3: 1, 4: 0}
PTS_APPEARANCE = 2

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
    """Fetch real xG/xA data from Understat for current season."""
    print("Fetching Understat xG data...")
    try:
        understat = UnderstatClient()
        # 2024 = 2024/25 season
        player_data = understat.league(league="EPL").get_player_data(season="2024")
        team_data = understat.league(league="EPL").get_team_data(season="2024")
        return player_data, team_data
    except Exception as e:
        print(f"Error fetching Understat data: {e}")
        return None, None


def match_player_names(fpl_name, fpl_team, understat_players, team_mapping):
    """
    Match FPL player to Understat player using fuzzy name matching.
    Returns Understat player data or None.
    """
    fpl_name_clean = fpl_name.lower().strip()
    best_match = None
    best_score = 0
    
    for us_player in understat_players:
        us_name = us_player.get('player_name', '').lower()
        us_team = us_player.get('team_name', '')
        
        # Check if teams match (using mapping)
        fpl_team_name = team_mapping.get(fpl_team, '').lower()
        if fpl_team_name and fpl_team_name not in us_team.lower():
            continue
        
        # Fuzzy match on name
        # Try matching last name (web_name in FPL is usually last name)
        score = SequenceMatcher(None, fpl_name_clean, us_name).ratio()
        
        # Also try if FPL name is contained in Understat name
        if fpl_name_clean in us_name or us_name.split()[-1] == fpl_name_clean:
            score = max(score, 0.85)
        
        if score > best_score and score > 0.6:
            best_score = score
            best_match = us_player
    
    return best_match


# =============================================================================
# TEAM STRENGTH (using Understat team xG data)
# =============================================================================

def calculate_team_strengths(understat_teams, fpl_teams):
    """
    Calculate team strengths using REAL xG data from Understat.
    Much better than FPL's arbitrary strength ratings.
    """
    team_strength = {}
    
    # Build FPL team name mapping
    fpl_team_names = {t['id']: t['name'] for t in fpl_teams}
    
    # Team name mapping (FPL name -> Understat name variations)
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
        
        # Find matching Understat team
        us_team = None
        if understat_teams:
            for t_id, t_data in understat_teams.items():
                if t_data.get('title', '').lower() == us_name.lower():
                    us_team = t_data
                    break
        
        if us_team and 'history' in us_team:
            history = us_team['history']
            if history:
                # Calculate actual xG and xGA per game
                total_xg = sum(float(h.get('xG', 0)) for h in history)
                total_xga = sum(float(h.get('xGA', 0)) for h in history)
                games = len(history)
                
                xg_per_game = total_xg / games if games > 0 else 1.3
                xga_per_game = total_xga / games if games > 0 else 1.3
                
                # Clean sheet probability based on xGA
                # Lower xGA = higher CS prob
                cs_prob = max(0.05, min(0.5, 0.6 - (xga_per_game * 0.25)))
                
                team_strength[team_id] = {
                    'name': fpl_name,
                    'short_name': fpl_team['short_name'],
                    'xg_per_game': round(xg_per_game, 2),
                    'xga_per_game': round(xga_per_game, 2),
                    'cs_prob': round(cs_prob, 3),
                    'attack_strength': xg_per_game / 1.3,  # Normalized to league avg
                    'defense_strength': xga_per_game / 1.3,
                }
            else:
                team_strength[team_id] = get_default_team_strength(fpl_team)
        else:
            team_strength[team_id] = get_default_team_strength(fpl_team)
    
    return team_strength


def get_default_team_strength(fpl_team):
    """Fallback if Understat data unavailable."""
    return {
        'name': fpl_team['name'],
        'short_name': fpl_team['short_name'],
        'xg_per_game': 1.3,
        'xga_per_game': 1.3,
        'cs_prob': 0.25,
        'attack_strength': 1.0,
        'defense_strength': 1.0,
    }


def get_fixture_difficulty(team_strengths, opponent_id, is_home):
    """
    Calculate fixture difficulty based on opponent's REAL defensive xGA.
    Lower opponent xGA = harder fixture = higher difficulty multiplier.
    """
    opp = team_strengths.get(opponent_id, {})
    opp_defense = opp.get('defense_strength', 1.0)
    
    # Home advantage adjustment
    home_boost = 0.9 if is_home else 1.1
    
    # Difficulty: good defense (low xGA) = harder
    # opp_defense < 1 means they concede less than average
    difficulty = opp_defense * home_boost
    
    return max(0.6, min(1.5, difficulty))


# =============================================================================
# PROJECTION CALCULATIONS (using real xG)
# =============================================================================

def calculate_player_xgi(fpl_player, understat_match, team_strengths):
    """
    Calculate expected goal involvement using REAL Understat xG/xA.
    """
    if not understat_match:
        # Fallback to FPL approximation if no Understat match
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
    
    # Use REAL Understat data
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
                            opponent_cs_prob, element_type, team_cs_prob):
    """
    Project points for a single gameweek using real xG data.
    """
    if xgi_stats is None:
        return 0
    
    # Availability check
    chance = player.get('chance_of_playing_next_round')
    if chance is not None and chance < 50:
        return 0
    availability = (chance / 100) if chance is not None else 0.95
    
    # Minutes probability
    avg_mins = xgi_stats.get('minutes', 0) / max(1, xgi_stats.get('games', 1))
    mins_prob = min(1.0, avg_mins / 70)
    
    # Expected goals adjusted for fixture
    # Lower difficulty = easier fixture = higher xG realization
    xg_adj = xgi_stats['xg_p90'] / fixture_difficulty
    xa_adj = xgi_stats['xa_p90'] / fixture_difficulty
    
    # Points calculation
    goal_pts = xg_adj * PTS_GOAL.get(element_type, 4)
    assist_pts = xa_adj * PTS_ASSIST
    
    # Clean sheet points (for DEF/GK)
    cs_pts = team_cs_prob * PTS_CLEAN_SHEET.get(element_type, 0)
    
    # Appearance (2 pts for 60+ mins)
    appearance_pts = PTS_APPEARANCE if mins_prob > 0.6 else 1
    
    # Bonus estimate based on xGI
    xgi = xg_adj + xa_adj
    if element_type in [1, 2]:  # GK/DEF get bonus for CS too
        bonus_pts = min(3, xgi * 1.5 + (team_cs_prob * 1.5))
    else:
        bonus_pts = min(3, xgi * 2.5) if xgi > 0.25 else 0
    
    total = goal_pts + assist_pts + cs_pts + appearance_pts + bonus_pts
    return round(total * availability * mins_prob, 2)


# =============================================================================
# TRANSFER LOGIC (improved)
# =============================================================================

def get_best_transfers(my_squad, all_players, projections, bank, free_transfers):
    """Find optimal transfers with improved logic."""
    recommendations = []
    
    # Get squad player IDs
    squad_ids = {p['element'] for p in my_squad}
    
    # Group all players by position with projections
    by_position = {1: [], 2: [], 3: [], 4: []}
    for p in all_players:
        if p['id'] in squad_ids:
            continue
        pos = p['element_type']
        proj = projections.get(p['id'], {})
        if proj.get('next_4gw_pts', 0) > 0:
            by_position[pos].append({
                'player': p,
                'proj_4gw': proj.get('next_4gw_pts', 0),
                'proj_1gw': proj.get('next_gw_pts', 0),
                'proj_6gw': proj.get('next_6gw_pts', 0),
                'xgi_quality': proj.get('data_quality', 'unknown'),
            })
    
    # Sort by 4GW projection
    for pos in by_position:
        by_position[pos].sort(key=lambda x: x['proj_4gw'], reverse=True)
    
    # Analyze squad weaknesses
    squad_analysis = []
    for pick in my_squad:
        player_id = pick['element']
        proj = projections.get(player_id, {})
        squad_analysis.append({
            'player_id': player_id,
            'position': pick.get('element_type', 0),
            'selling_price': pick.get('selling_price', 0) / 10,
            'name': pick.get('web_name', 'Unknown'),
            'proj_4gw': proj.get('next_4gw_pts', 0),
            'proj_1gw': proj.get('next_gw_pts', 0),
            'is_starter': pick.get('multiplier', 0) > 0,
        })
    
    # Sort by projected points (worst first)
    squad_analysis.sort(key=lambda x: (x['is_starter'], x['proj_4gw']))
    
    # Find upgrade opportunities
    for weak in squad_analysis[:5]:  # Check bottom 5
        pos = weak['position']
        if pos == 0:
            continue
            
        budget = bank + weak['selling_price']
        
        for candidate in by_position.get(pos, [])[:15]:
            cand = candidate['player']
            cost = cand['now_cost'] / 10
            
            if cost > budget:
                continue
            
            gain_4gw = candidate['proj_4gw'] - weak['proj_4gw']
            gain_1gw = candidate['proj_1gw'] - weak['proj_1gw']
            
            # Is it worth a hit?
            hit_value = gain_4gw - (4 * PLANNING_HORIZON / HIT_THRESHOLD_GWS)
            worth_hit = hit_value > 0
            
            if gain_4gw > 1.5:  # At least 1.5 pts gain over 4 GW
                recommendations.append({
                    'out_id': weak['player_id'],
                    'out_name': weak['name'],
                    'in_id': cand['id'],
                    'in_name': cand['web_name'],
                    'in_team': cand['team'],
                    'in_cost': cost,
                    'gain_4gw': round(gain_4gw, 1),
                    'gain_1gw': round(gain_1gw, 1),
                    'worth_hit': worth_hit,
                    'hit_value': round(hit_value, 1),
                    'position': pos,
                    'data_quality': candidate['xgi_quality'],
                })
                break
    
    recommendations.sort(key=lambda x: x['gain_4gw'], reverse=True)
    return recommendations[:5]


# =============================================================================
# CAPTAIN SELECTION
# =============================================================================

def get_captain_picks(my_squad, projections, all_players):
    """Rank captain options with ownership data for differential analysis."""
    captain_options = []
    player_lookup = {p['id']: p for p in all_players}
    
    for pick in my_squad:
        if pick.get('multiplier', 0) == 0:  # Skip bench
            continue
            
        player_id = pick['element']
        proj = projections.get(player_id, {})
        player = player_lookup.get(player_id, {})
        
        proj_pts = proj.get('next_gw_pts', 0)
        if proj_pts > 2:
            ownership = float(player.get('selected_by_percent', 0))
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
                'is_differential': ownership < 15,
                'data_quality': proj.get('data_quality', 'unknown'),
            })
    
    captain_options.sort(key=lambda x: x['projected_pts'], reverse=True)
    return captain_options[:5]


# =============================================================================
# CHIP ANALYSIS
# =============================================================================

def analyze_chip_timing(fixtures, current_gw):
    """Detect DGW/BGW and recommend chip usage."""
    recommendations = []
    
    gw_fixtures = {}
    for f in fixtures:
        gw = f.get('event')
        if gw and gw >= current_gw:
            if gw not in gw_fixtures:
                gw_fixtures[gw] = []
            gw_fixtures[gw].append(f)
    
    for gw in sorted(gw_fixtures.keys()):
        if gw > current_gw + 10:
            break
            
        count = len(gw_fixtures[gw])
        
        if count > 10:
            recommendations.append({
                'gameweek': gw,
                'type': 'double',
                'fixtures': count,
                'chip_suggestion': 'Bench Boost or Triple Captain',
                'priority': 'HIGH' if count >= 12 else 'MEDIUM',
                'notes': f'GW{gw} has {count} fixtures. Stack DGW players and consider BB if bench is strong, TC on premium with 2 good fixtures.'
            })
        elif count < 10:
            recommendations.append({
                'gameweek': gw,
                'type': 'blank',
                'fixtures': count,
                'chip_suggestion': 'Free Hit candidate',
                'priority': 'HIGH' if count <= 6 else 'MEDIUM',
                'notes': f'GW{gw} has only {count} fixtures. Check squad coverage - Free Hit if fewer than 8 players have games.'
            })
    
    return recommendations


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def run_projections():
    print("=" * 60)
    print("FPL BRAIN v2 - Projection Engine")
    print("=" * 60)
    
    # Fetch all data
    print("\nFetching FPL data...")
    bootstrap = fetch_json(BOOTSTRAP_URL)
    fixtures = fetch_json(FIXTURES_URL)
    
    if not bootstrap or not fixtures:
        print("Failed to fetch FPL data!")
        return
    
    players = bootstrap['elements']
    teams = bootstrap['teams']
    events = bootstrap['events']
    
    # Get Understat data
    understat_players, understat_teams = get_understat_data()
    
    # Find current/next gameweek
    current_gw = next((e['id'] for e in events if e['is_current']), 1)
    next_gw = next((e['id'] for e in events if e['is_next']), current_gw + 1)
    print(f"Current GW: {current_gw}, Next GW: {next_gw}")
    
    # Calculate team strengths from Understat
    team_strengths = calculate_team_strengths(understat_teams, teams)
    team_lookup = {t['id']: t for t in teams}
    
    # Build team name mapping for player matching
    team_name_map = {t['id']: t['name'] for t in teams}
    
    # Get upcoming fixtures per team
    upcoming = {}
    for f in fixtures:
        gw = f.get('event')
        if gw and gw >= next_gw and gw < next_gw + 6:
            for team_id, is_home in [(f['team_h'], True), (f['team_a'], False)]:
                if team_id not in upcoming:
                    upcoming[team_id] = []
                opp_id = f['team_a'] if is_home else f['team_h']
                upcoming[team_id].append({
                    'gw': gw,
                    'opponent_id': opp_id,
                    'opponent': team_lookup.get(opp_id, {}).get('short_name', '?'),
                    'is_home': is_home,
                    'difficulty': get_fixture_difficulty(team_strengths, opp_id, is_home)
                })
    
    # Calculate projections
    print("Calculating projections with real xG data...")
    projections = {}
    matched_count = 0
    
    for player in players:
        player_id = player['id']
        team_id = player['team']
        element_type = player['element_type']
        
        # Try to match with Understat player
        us_match = None
        if understat_players:
            us_match = match_player_names(
                player['web_name'], 
                team_id, 
                understat_players,
                team_name_map
            )
            if us_match:
                matched_count += 1
        
        # Calculate xGI stats
        xgi_stats = calculate_player_xgi(player, us_match, team_strengths)
        
        if xgi_stats is None:
            continue
        
        # Get fixtures
        team_fixtures = upcoming.get(team_id, [])
        team_cs_prob = team_strengths.get(team_id, {}).get('cs_prob', 0.2)
        
        # Project each gameweek
        gw_projections = []
        for fix in team_fixtures[:6]:
            opp_cs_prob = team_strengths.get(fix['opponent_id'], {}).get('cs_prob', 0.2)
            pts = project_gameweek_points(
                player, xgi_stats, fix['difficulty'],
                opp_cs_prob, element_type, team_cs_prob
            )
            gw_projections.append({
                'gw': fix['gw'],
                'projected_pts': pts,
                'opponent': fix['opponent'],
                'is_home': fix['is_home'],
                'difficulty': round(fix['difficulty'], 2)
            })
        
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
            'xg_p90': round(xgi_stats.get('xg_p90', 0), 3),
            'xa_p90': round(xgi_stats.get('xa_p90', 0), 3),
            'next_gw_pts': next_fix.get('projected_pts', 0),
            'next_fixture': f"{'(H)' if next_fix.get('is_home') else '(A)'} {next_fix.get('opponent', '?')}",
            'next_fixture_diff': next_fix.get('difficulty', 1.0),
            'next_4gw_pts': round(sum(g['projected_pts'] for g in gw_projections[:4]), 1),
            'next_6gw_pts': round(sum(g['projected_pts'] for g in gw_projections[:6]), 1),
            'fixtures': gw_projections,
            'data_quality': xgi_stats.get('data_quality', 'unknown'),
        }
    
    print(f"Matched {matched_count}/{len(players)} players with Understat data")
    
    # Get user's team
    print("Fetching your team...")
    my_team_data = fetch_json(PICKS_URL.format(gw=current_gw))
    my_entry = fetch_json(TEAM_URL)
    
    transfers = []
    captains = []
    my_team_output = None
    
    if my_team_data and my_entry:
        my_picks = my_team_data.get('picks', [])
        
        for pick in my_picks:
            p = next((pl for pl in players if pl['id'] == pick['element']), {})
            pick['element_type'] = p.get('element_type', 0)
            pick['web_name'] = p.get('web_name', 'Unknown')
            pick['selling_price'] = pick.get('selling_price', p.get('now_cost', 0))
        
        bank = my_entry.get('last_deadline_bank', 0) / 10
        
        transfers = get_best_transfers(my_picks, players, projections, bank, 1)
        captains = get_captain_picks(my_picks, projections, players)
        
        my_team_output = {
            'team_id': TEAM_ID,
            'current_gw': current_gw,
            'next_gw': next_gw,
            'bank': round(bank, 1),
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
            'total_projected_pts': round(sum(
                projections.get(p['element'], {}).get('next_gw_pts', 0) * p['multiplier']
                for p in my_picks if p['multiplier'] > 0
            ), 1),
        }
    
    chip_analysis = analyze_chip_timing(fixtures, next_gw)
    
    # Build outputs
    recommendations = {
        'generated_at': datetime.utcnow().isoformat(),
        'next_gameweek': next_gw,
        'data_source': f"Understat ({matched_count} players matched)",
        'captain_picks': captains,
        'transfer_recommendations': transfers,
        'chip_analysis': chip_analysis,
    }
    
    # Top players by position
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
    
    print(f"\n{'=' * 60}")
    print("RESULTS")
    print('=' * 60)
    print(f"Files written to {output_dir}/")
    
    if captains:
        print(f"\n🎯 Top Captain: {captains[0]['name']} ({captains[0]['projected_pts']:.1f} pts)")
    if transfers:
        t = transfers[0]
        print(f"📈 Top Transfer: {t['out_name']} → {t['in_name']} (+{t['gain_4gw']} pts/4GW)")
        if t['worth_hit']:
            print(f"   ⚡ Worth a -4 hit!")
    
    print("\nDone!")


if __name__ == '__main__':
    run_projections()
