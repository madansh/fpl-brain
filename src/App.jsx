import { useState, useEffect } from 'react';

const POS_LABELS = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
const POS_COLORS = { 1: 'bg-yellow-500', 2: 'bg-green-500', 3: 'bg-blue-500', 4: 'bg-red-500' };

function DifficultyBadge({ difficulty, small = false }) {
  if (!difficulty) return null;
  const label = difficulty < 0.85 ? 'Easy' : difficulty > 1.15 ? 'Hard' : 'Med';
  const color = difficulty < 0.85 ? 'bg-green-100 text-green-700' :
                difficulty > 1.15 ? 'bg-red-100 text-red-700' :
                'bg-yellow-100 text-yellow-700';
  const size = small ? 'px-1 py-0.5 text-xs' : 'px-2 py-0.5 text-xs';
  return <span className={`${size} rounded font-medium ${color}`}>{label}</span>;
}

function FormBadge({ trend }) {
  if (trend === 'hot') return <span className="text-orange-500" title="Hot form">🔥</span>;
  if (trend === 'cold') return <span className="text-blue-400" title="Cold form">🥶</span>;
  return null;
}

function FixtureRun({ fixtures }) {
  if (!fixtures?.length) return null;
  return (
    <div className="flex gap-1">
      {fixtures.slice(0, 4).map((f, i) => (
        <div key={i} className={`text-xs px-1.5 py-0.5 rounded ${
          f.is_dgw ? 'bg-purple-100 text-purple-700 font-bold' :
          f.difficulty < 0.85 ? 'bg-green-100 text-green-700' :
          f.difficulty > 1.15 ? 'bg-red-100 text-red-700' :
          'bg-gray-100 text-gray-600'
        }`} title={f.fixture}>
          {f.is_dgw ? 'DGW' : f.fixture?.split(' ')[0]?.slice(0, 3) || '?'}
        </div>
      ))}
    </div>
  );
}

function ReasonTags({ reasons, type }) {
  const colorMap = {
    'hot_form': 'bg-orange-100 text-orange-700',
    'cold_form': 'bg-blue-100 text-blue-700',
    'easy_fixtures': 'bg-green-100 text-green-700',
    'hard_fixtures': 'bg-red-100 text-red-700',
    'injury_doubt': 'bg-red-100 text-red-700',
    'low_projection': 'bg-gray-100 text-gray-600',
  };
  const labelMap = {
    'hot_form': '🔥 Hot',
    'cold_form': '🥶 Cold',
    'easy_fixtures': '📅 Easy run',
    'hard_fixtures': '📅 Hard run',
    'injury_doubt': '🏥 Injury',
    'low_projection': '📉 Low pts',
  };
  
  return (
    <div className="flex flex-wrap gap-1">
      {reasons?.map((r, i) => {
        const isDGW = r.startsWith('dgw');
        const isBGW = r.startsWith('blank');
        if (isDGW) {
          return <span key={i} className="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700 font-medium">🎯 {r.toUpperCase()}</span>;
        }
        if (isBGW) {
          return <span key={i} className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 text-yellow-700">⚠️ {r}</span>;
        }
        return (
          <span key={i} className={`px-1.5 py-0.5 text-xs rounded ${colorMap[r] || 'bg-gray-100 text-gray-600'}`}>
            {labelMap[r] || r}
          </span>
        );
      })}
    </div>
  );
}

function CaptainCard({ pick, rank }) {
  const isTop = rank === 1;
  return (
    <div className={`p-4 rounded-lg border-2 ${isTop ? 'border-yellow-400 bg-gradient-to-r from-yellow-50 to-orange-50' : 'border-gray-200 bg-white'}`}>
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2">
            {isTop && <span className="text-xl">👑</span>}
            <h3 className="font-bold text-lg">{pick.name}</h3>
            <FormBadge trend={pick.form_trend} />
            {pick.has_dgw && <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full font-medium">DGW</span>}
            {pick.is_differential && <span className="px-2 py-0.5 bg-blue-100 text-blue-700 text-xs rounded-full">Diff</span>}
          </div>
          <p className="text-gray-600 text-sm">{pick.team} • {pick.fixture}</p>
        </div>
        <div className="text-right">
          <p className="text-3xl font-bold text-blue-600">{pick.projected_pts.toFixed(1)}</p>
          <p className="text-sm text-gray-500">×2 = {pick.doubled_pts}</p>
        </div>
      </div>
      <div className="mt-3 flex flex-wrap gap-3 text-sm items-center">
        <span className="text-gray-600">Own: {pick.ownership}%</span>
        <DifficultyBadge difficulty={pick.fixture_difficulty} />
      </div>
    </div>
  );
}

function TransferCard({ transfer }) {
  return (
    <div className="p-4 rounded-lg border border-gray-200 bg-white hover:shadow-md transition-shadow">
      <div className="flex items-center gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-red-500 text-xs font-medium">OUT</p>
          <p className="font-semibold text-gray-700 truncate">{transfer.out_name}</p>
          <ReasonTags reasons={transfer.out_reasons} type="out" />
        </div>
        <div className="text-2xl text-gray-300">→</div>
        <div className="flex-1 min-w-0">
          <p className="text-green-500 text-xs font-medium">IN</p>
          <p className="font-semibold truncate">{transfer.in_name}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-gray-500 text-sm">£{transfer.in_cost}m</span>
            <span className="text-gray-400 text-xs">({transfer.value_score} pts/£m)</span>
          </div>
          <ReasonTags reasons={transfer.buy_reasons} type="in" />
        </div>
        <div className="text-right pl-4 border-l">
          <p className="text-2xl font-bold text-green-600">+{transfer.gain_4gw}</p>
          <p className="text-xs text-gray-500">pts / 4GW</p>
        </div>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <FixtureRun fixtures={transfer.fixtures} />
        {transfer.worth_hit && (
          <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
            ⚡ Worth -4 (net +{transfer.hit_value})
          </span>
        )}
      </div>
    </div>
  );
}

function ChipCard({ chip }) {
  const colors = {
    'Bench Boost': 'from-green-500 to-emerald-600',
    'Triple Captain': 'from-purple-500 to-indigo-600',
    'Free Hit': 'from-orange-500 to-red-500',
    'Wildcard': 'from-blue-500 to-cyan-600',
  };
  const icons = {
    'Bench Boost': '🪑',
    'Triple Captain': '👑',
    'Free Hit': '⚡',
    'Wildcard': '🃏',
  };
  
  return (
    <div className={`rounded-xl overflow-hidden bg-gradient-to-r ${colors[chip.chip] || 'from-gray-500 to-gray-600'}`}>
      <div className="p-4 text-white">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">{icons[chip.chip]}</span>
            <div>
              <h3 className="font-bold text-lg">{chip.chip}</h3>
              <p className="text-white/80 text-sm">Recommended: GW{chip.recommended_gw}</p>
            </div>
          </div>
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${
            chip.confidence === 'HIGH' ? 'bg-white/30' : 'bg-white/20'
          }`}>
            {chip.confidence}
          </span>
        </div>
        {chip.recommended_player && (
          <p className="mt-2 text-white/90 text-sm">
            Player: <strong>{chip.recommended_player}</strong>
          </p>
        )}
      </div>
      <div className="bg-white p-4">
        <p className="text-gray-700 text-sm">{chip.reasoning}</p>
        <p className="text-gray-500 text-xs mt-2 italic">💡 {chip.action_needed}</p>
      </div>
    </div>
  );
}

function SquadView({ squad }) {
  const starters = squad?.filter(p => p.multiplier > 0) || [];
  const bench = squad?.filter(p => p.multiplier === 0) || [];

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-bold text-gray-700 mb-3">Starting XI</h3>
        <div className="grid gap-2">
          {starters
            .sort((a, b) => a.position - b.position || b.projected_pts - a.projected_pts)
            .map(player => (
              <div key={player.player_id} className="p-3 rounded-lg bg-white border flex justify-between items-center">
                <div className="flex items-center gap-3">
                  <span className={`w-10 h-10 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center font-medium`}>
                    {POS_LABELS[player.position]}
                  </span>
                  <div>
                    <div className="flex items-center gap-1">
                      <p className="font-medium">
                        {player.name}
                        {player.is_captain && <span className="ml-1 text-yellow-600">(C)</span>}
                        {player.is_vice && <span className="ml-1 text-gray-400">(V)</span>}
                      </p>
                      <FormBadge trend={player.form_trend} />
                    </div>
                    <FixtureRun fixtures={player.fixture_preview} />
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold">{player.projected_pts?.toFixed(1)}</p>
                  <p className="text-xs text-gray-500">{player.projected_4gw?.toFixed(1)} (4GW)</p>
                </div>
              </div>
            ))}
        </div>
      </div>
      
      <div>
        <h3 className="font-bold text-gray-500 mb-3">Bench</h3>
        <div className="grid gap-2 opacity-70">
          {bench.map(player => (
            <div key={player.player_id} className="p-3 rounded-lg bg-gray-50 border border-dashed flex justify-between items-center">
              <div className="flex items-center gap-3">
                <span className={`w-8 h-8 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center`}>
                  {POS_LABELS[player.position]}
                </span>
                <div>
                  <p className="font-medium text-gray-600">{player.name}</p>
                  <FixtureRun fixtures={player.fixture_preview} />
                </div>
              </div>
              <p className="font-bold text-gray-600">{player.projected_pts?.toFixed(1)}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TopPlayersTable({ players, title }) {
  if (!players?.length) return null;
  
  return (
    <div className="bg-white rounded-lg border overflow-hidden">
      <h3 className="font-bold text-lg p-4 border-b bg-gray-50">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-gray-50">
              <th className="text-left py-3 px-4">Player</th>
              <th className="text-left py-3 px-2">Team</th>
              <th className="text-right py-3 px-2">£</th>
              <th className="text-right py-3 px-2">xG</th>
              <th className="text-right py-3 px-2">xA</th>
              <th className="text-right py-3 px-2">Next</th>
              <th className="text-right py-3 px-2 font-bold">4GW</th>
              <th className="text-left py-3 px-4">Fixtures</th>
            </tr>
          </thead>
          <tbody>
            {players.slice(0, 12).map((p, i) => (
              <tr key={p.player_id} className={`border-b hover:bg-blue-50 ${i < 3 ? 'bg-green-50' : ''}`}>
                <td className="py-3 px-4">
                  <div className="flex items-center gap-1">
                    <span className="font-medium">{p.name}</span>
                    <FormBadge trend={p.form_trend} />
                    {p.has_dgw_soon && <span className="text-purple-500 text-xs">DGW</span>}
                    {p.news && <span className="text-orange-500" title={p.news}>⚠️</span>}
                  </div>
                </td>
                <td className="py-3 px-2 text-gray-600">{p.team}</td>
                <td className="py-3 px-2 text-right">{p.price}</td>
                <td className="py-3 px-2 text-right font-mono text-gray-600">{p.xg_p90?.toFixed(2)}</td>
                <td className="py-3 px-2 text-right font-mono text-gray-600">{p.xa_p90?.toFixed(2)}</td>
                <td className="py-3 px-2 text-right">{p.next_gw_pts?.toFixed(1)}</td>
                <td className="py-3 px-2 text-right font-bold text-blue-600">{p.next_4gw_pts?.toFixed(1)}</td>
                <td className="py-3 px-4">
                  <FixtureRun fixtures={p.fixture_preview} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function App() {
  const [recommendations, setRecommendations] = useState(null);
  const [myTeam, setMyTeam] = useState(null);
  const [projections, setProjections] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch('/data/recommendations.json').then(r => r.ok ? r.json() : null),
      fetch('/data/my_team.json').then(r => r.ok ? r.json() : null),
      fetch('/data/projections.json').then(r => r.ok ? r.json() : null),
    ]).then(([recs, team, proj]) => {
      setRecommendations(recs);
      setMyTeam(team);
      setProjections(proj);
      setLoading(false);
    });
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-purple-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading projections...</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: '🎯 Overview' },
    { id: 'chips', label: '🎮 Chips' },
    { id: 'squad', label: '👥 Squad' },
    { id: 'players', label: '📊 Players' },
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-gradient-to-r from-purple-700 via-purple-600 to-blue-600 text-white p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold">FPL Brain</h1>
          <div className="flex flex-wrap gap-3 mt-2 text-sm text-purple-200">
            <span>GW{recommendations?.next_gameweek || '?'}</span>
            <span>•</span>
            <span>{recommendations?.data_source}</span>
            {recommendations?.fixture_alerts?.dgw_gws?.length > 0 && (
              <>
                <span>•</span>
                <span className="text-yellow-300">DGWs: {recommendations.fixture_alerts.dgw_gws.join(', ')}</span>
              </>
            )}
          </div>
        </div>
      </header>

      <nav className="bg-white border-b sticky top-0 z-10 shadow-sm">
        <div className="max-w-4xl mx-auto flex overflow-x-auto">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-4 font-medium whitespace-nowrap transition-all ${
                activeTab === tab.id 
                  ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50' 
                  : 'text-gray-600 hover:text-gray-900'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="max-w-4xl mx-auto p-4 space-y-6">
        {activeTab === 'overview' && (
          <>
            {myTeam && (
              <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white">
                <div className="flex justify-between items-start">
                  <div>
                    <p className="text-blue-100 text-sm">GW{recommendations?.next_gameweek} Projected</p>
                    <p className="text-5xl font-bold mt-1">{myTeam.total_projected_pts} pts</p>
                  </div>
                  <div className="text-right text-sm">
                    <p className="text-blue-200">Bank: £{myTeam.bank}m</p>
                    <p className="text-blue-200 mt-1">Chips: {myTeam.chips_available?.length || 0}</p>
                  </div>
                </div>
              </div>
            )}

            <section>
              <h2 className="text-xl font-bold mb-4">👑 Captain Picks</h2>
              <div className="space-y-3">
                {recommendations?.captain_picks?.map((pick, i) => (
                  <CaptainCard key={pick.player_id} pick={pick} rank={i + 1} />
                ))}
              </div>
            </section>

            <section>
              <h2 className="text-xl font-bold mb-4">📈 Transfer Recommendations</h2>
              <div className="space-y-3">
                {recommendations?.transfer_recommendations?.length > 0 ? (
                  recommendations.transfer_recommendations.map((transfer, i) => (
                    <TransferCard key={i} transfer={transfer} />
                  ))
                ) : (
                  <div className="bg-white p-6 rounded-lg border text-center">
                    <p className="text-2xl mb-2">💪</p>
                    <p className="text-gray-600">No urgent transfers - squad looks solid!</p>
                  </div>
                )}
              </div>
            </section>
          </>
        )}

        {activeTab === 'chips' && (
          <section>
            <h2 className="text-xl font-bold mb-4">🎮 Chip Strategy</h2>
            {recommendations?.chip_strategy?.length > 0 ? (
              <div className="space-y-4">
                {recommendations.chip_strategy.map((chip, i) => (
                  <ChipCard key={i} chip={chip} />
                ))}
              </div>
            ) : (
              <div className="bg-white p-6 rounded-lg border text-center">
                <p className="text-gray-600">No chip recommendations yet. Check back closer to DGWs/BGWs.</p>
              </div>
            )}
            
            {myTeam?.chips_available && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-medium text-gray-700 mb-2">Available Chips</h3>
                <div className="flex flex-wrap gap-2">
                  {myTeam.chips_available.map(chip => (
                    <span key={chip} className="px-3 py-1 bg-white border rounded-full text-sm">
                      {chip.replace('_', ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </section>
        )}

        {activeTab === 'squad' && myTeam && (
          <SquadView squad={myTeam.squad} />
        )}

        {activeTab === 'players' && projections?.top_by_position && (
          <div className="space-y-6">
            {['FWD', 'MID', 'DEF', 'GK'].map(pos => (
              <TopPlayersTable 
                key={pos} 
                players={projections.top_by_position[pos]} 
                title={pos === 'GK' ? 'Goalkeepers' : pos === 'DEF' ? 'Defenders' : pos === 'MID' ? 'Midfielders' : 'Forwards'}
              />
            ))}
          </div>
        )}
      </main>

      <footer className="text-center py-8 text-gray-400 text-sm">
        <p>Built for top 100 🏆</p>
        <p className="mt-1">FPL API + Understat xG • Updates daily 6am UTC</p>
      </footer>
    </div>
  );
}
