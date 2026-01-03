import { useState, useEffect } from 'react';

const POS_LABELS = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
const POS_COLORS = { 
  1: 'bg-yellow-500', 
  2: 'bg-green-500', 
  3: 'bg-blue-500', 
  4: 'bg-red-500' 
};

function DifficultyBadge({ difficulty }) {
  const label = difficulty < 0.85 ? 'Easy' : difficulty > 1.15 ? 'Hard' : 'Medium';
  const color = difficulty < 0.85 ? 'bg-green-100 text-green-800' :
                difficulty > 1.15 ? 'bg-red-100 text-red-800' :
                'bg-yellow-100 text-yellow-800';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {label}
    </span>
  );
}

function DataQualityBadge({ quality }) {
  if (quality === 'understat') {
    return <span className="text-xs text-green-600">✓ xG data</span>;
  }
  return <span className="text-xs text-gray-400">~ estimated</span>;
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
            {pick.is_differential && (
              <span className="px-2 py-0.5 bg-purple-100 text-purple-700 text-xs rounded-full">
                Differential
              </span>
            )}
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
        <span className="text-gray-600">Form: {pick.form}</span>
        <DifficultyBadge difficulty={pick.fixture_difficulty} />
        <DataQualityBadge quality={pick.data_quality} />
      </div>
    </div>
  );
}

function TransferCard({ transfer }) {
  return (
    <div className="p-4 rounded-lg border border-gray-200 bg-white hover:shadow-md transition-shadow">
      <div className="flex items-center gap-4">
        <div className="flex-1">
          <p className="text-red-500 text-xs font-medium">OUT</p>
          <p className="font-semibold text-gray-700">{transfer.out_name}</p>
        </div>
        <div className="text-2xl text-gray-300">→</div>
        <div className="flex-1">
          <p className="text-green-500 text-xs font-medium">IN</p>
          <p className="font-semibold">{transfer.in_name}</p>
          <p className="text-gray-500 text-sm">£{transfer.in_cost}m</p>
        </div>
        <div className="text-right pl-4 border-l">
          <p className="text-2xl font-bold text-green-600">+{transfer.gain_4gw}</p>
          <p className="text-xs text-gray-500">pts / 4GW</p>
        </div>
      </div>
      <div className="mt-3 flex gap-2">
        {transfer.worth_hit && (
          <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
            ⚡ Worth a -4 (net +{transfer.hit_value})
          </span>
        )}
        <DataQualityBadge quality={transfer.data_quality} />
      </div>
    </div>
  );
}

function SquadView({ squad }) {
  const positions = [
    { pos: 1, label: 'Goalkeepers' },
    { pos: 2, label: 'Defenders' },
    { pos: 3, label: 'Midfielders' },
    { pos: 4, label: 'Forwards' },
  ];

  const starters = squad.filter(p => p.multiplier > 0);
  const bench = squad.filter(p => p.multiplier === 0);

  return (
    <div className="space-y-6">
      <div>
        <h3 className="font-bold text-gray-700 mb-3">Starting XI</h3>
        <div className="grid gap-2">
          {starters
            .sort((a, b) => a.position - b.position || b.projected_pts - a.projected_pts)
            .map(player => (
              <div 
                key={player.player_id}
                className="p-3 rounded-lg bg-white border flex justify-between items-center"
              >
                <div className="flex items-center gap-3">
                  <span className={`w-10 h-10 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center font-medium`}>
                    {POS_LABELS[player.position]}
                  </span>
                  <div>
                    <p className="font-medium">
                      {player.name}
                      {player.is_captain && <span className="ml-1 text-yellow-600">(C)</span>}
                      {player.is_vice && <span className="ml-1 text-gray-400">(V)</span>}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-lg font-bold">{player.projected_pts.toFixed(1)}</p>
                  <p className="text-xs text-gray-500">{player.projected_4gw.toFixed(1)} (4GW)</p>
                </div>
              </div>
            ))}
        </div>
      </div>
      
      <div>
        <h3 className="font-bold text-gray-500 mb-3">Bench</h3>
        <div className="grid gap-2 opacity-70">
          {bench.map(player => (
            <div 
              key={player.player_id}
              className="p-3 rounded-lg bg-gray-50 border border-dashed flex justify-between items-center"
            >
              <div className="flex items-center gap-3">
                <span className={`w-8 h-8 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center`}>
                  {POS_LABELS[player.position]}
                </span>
                <p className="font-medium text-gray-600">{player.name}</p>
              </div>
              <div className="text-right">
                <p className="font-bold text-gray-600">{player.projected_pts.toFixed(1)}</p>
              </div>
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
              <th className="text-right py-3 px-2">Price</th>
              <th className="text-right py-3 px-2">Own%</th>
              <th className="text-right py-3 px-2">xG/90</th>
              <th className="text-right py-3 px-2">xA/90</th>
              <th className="text-right py-3 px-2 font-bold">Next</th>
              <th className="text-right py-3 px-2 font-bold">4GW</th>
              <th className="text-left py-3 px-4">Fixture</th>
            </tr>
          </thead>
          <tbody>
            {players.slice(0, 12).map((p, i) => (
              <tr key={p.player_id} className={`border-b hover:bg-blue-50 ${i < 3 ? 'bg-green-50' : ''}`}>
                <td className="py-3 px-4">
                  <span className="font-medium">{p.name}</span>
                  {p.news && <span className="ml-1 text-orange-500" title={p.news}>⚠️</span>}
                </td>
                <td className="py-3 px-2 text-gray-600">{p.team}</td>
                <td className="py-3 px-2 text-right">£{p.price}m</td>
                <td className="py-3 px-2 text-right text-gray-600">{p.ownership}%</td>
                <td className="py-3 px-2 text-right font-mono text-gray-600">{p.xg_p90?.toFixed(2) || '-'}</td>
                <td className="py-3 px-2 text-right font-mono text-gray-600">{p.xa_p90?.toFixed(2) || '-'}</td>
                <td className="py-3 px-2 text-right font-bold">{p.next_gw_pts?.toFixed(1)}</td>
                <td className="py-3 px-2 text-right font-bold text-blue-600">{p.next_4gw_pts?.toFixed(1)}</td>
                <td className="py-3 px-4">
                  <span className="flex items-center gap-2">
                    {p.next_fixture}
                    <DifficultyBadge difficulty={p.next_fixture_diff} />
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChipAlert({ chip }) {
  const isDGW = chip.type === 'double';
  const bgColor = isDGW ? 'bg-gradient-to-r from-green-50 to-emerald-50 border-green-300' : 'bg-gradient-to-r from-yellow-50 to-orange-50 border-yellow-300';
  
  return (
    <div className={`p-4 rounded-lg border-2 ${bgColor}`}>
      <div className="flex items-start gap-3">
        <span className="text-3xl">{isDGW ? '📈' : '⚠️'}</span>
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h4 className="font-bold text-lg">GW{chip.gameweek}</h4>
            <span className={`px-2 py-0.5 rounded text-xs font-medium ${
              chip.priority === 'HIGH' ? 'bg-red-100 text-red-700' : 'bg-yellow-100 text-yellow-700'
            }`}>
              {chip.priority}
            </span>
          </div>
          <p className="text-sm text-gray-700 mt-1">{chip.notes}</p>
          <p className="text-sm font-semibold mt-2 text-blue-700">💡 {chip.chip_suggestion}</p>
        </div>
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
  const [error, setError] = useState(null);

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
    }).catch(e => {
      setError(e.message);
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
    { id: 'squad', label: '👥 My Squad' },
    { id: 'players', label: '📊 Top Players' },
  ];

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-gradient-to-r from-purple-700 via-purple-600 to-blue-600 text-white p-6">
        <div className="max-w-4xl mx-auto">
          <h1 className="text-3xl font-bold">FPL Brain</h1>
          <p className="text-purple-200 mt-1">
            GW{recommendations?.next_gameweek || '?'} • 
            {recommendations?.data_source && ` ${recommendations.data_source} • `}
            Updated {recommendations?.generated_at ? new Date(recommendations.generated_at).toLocaleString() : 'N/A'}
          </p>
        </div>
      </header>

      <nav className="bg-white border-b sticky top-0 z-10 shadow-sm">
        <div className="max-w-4xl mx-auto flex">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-4 font-medium transition-all ${
                activeTab === tab.id 
                  ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50' 
                  : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
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
            {/* Projected Points Summary */}
            {myTeam && (
              <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white">
                <p className="text-blue-100 text-sm">GW{recommendations?.next_gameweek} Projected Total</p>
                <p className="text-5xl font-bold mt-1">{myTeam.total_projected_pts} pts</p>
                <p className="text-blue-200 mt-2">Bank: £{myTeam.bank}m</p>
              </div>
            )}

            {/* Captain Picks */}
            <section>
              <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
                👑 Captain Picks
              </h2>
              <div className="space-y-3">
                {recommendations?.captain_picks?.map((pick, i) => (
                  <CaptainCard key={pick.player_id} pick={pick} rank={i + 1} />
                ))}
                {!recommendations?.captain_picks?.length && (
                  <p className="text-gray-500 bg-white p-4 rounded-lg">No captain data available</p>
                )}
              </div>
            </section>

            {/* Transfer Recommendations */}
            <section>
              <h2 className="text-xl font-bold mb-4">📈 Transfer Recommendations</h2>
              <div className="space-y-3">
                {recommendations?.transfer_recommendations?.map((transfer, i) => (
                  <TransferCard key={i} transfer={transfer} />
                ))}
                {!recommendations?.transfer_recommendations?.length && (
                  <div className="bg-white p-6 rounded-lg border text-center">
                    <p className="text-2xl mb-2">💪</p>
                    <p className="text-gray-600">No transfers recommended - your squad looks strong!</p>
                  </div>
                )}
              </div>
            </section>

            {/* Chip Analysis */}
            {recommendations?.chip_analysis?.length > 0 && (
              <section>
                <h2 className="text-xl font-bold mb-4">🎮 Chip Opportunities</h2>
                <div className="space-y-3">
                  {recommendations.chip_analysis.map((chip, i) => (
                    <ChipAlert key={i} chip={chip} />
                  ))}
                </div>
              </section>
            )}
          </>
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
                title={`Top ${pos === 'GK' ? 'Goalkeepers' : pos === 'DEF' ? 'Defenders' : pos === 'MID' ? 'Midfielders' : 'Forwards'}`}
              />
            ))}
          </div>
        )}
      </main>

      <footer className="text-center py-8 text-gray-400 text-sm">
        <p>Built for top 100 glory 🏆</p>
        <p className="mt-1">Data: FPL API + Understat xG • Updates daily at 6am UTC</p>
      </footer>
    </div>
  );
}
