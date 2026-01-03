import { useState, useEffect } from 'react';

// Position labels
const POS_LABELS = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
const POS_COLORS = { 
  1: 'bg-yellow-500', 
  2: 'bg-green-500', 
  3: 'bg-blue-500', 
  4: 'bg-red-500' 
};

function DifficultyBadge({ difficulty }) {
  const color = difficulty < 0.9 ? 'bg-green-100 text-green-800' :
                difficulty > 1.1 ? 'bg-red-100 text-red-800' :
                'bg-gray-100 text-gray-800';
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${color}`}>
      {difficulty < 0.9 ? 'Easy' : difficulty > 1.1 ? 'Hard' : 'Mid'}
    </span>
  );
}

function CaptainCard({ pick, rank }) {
  return (
    <div className={`p-4 rounded-lg border-2 ${rank === 1 ? 'border-yellow-400 bg-yellow-50' : 'border-gray-200 bg-white'}`}>
      <div className="flex justify-between items-start">
        <div>
          <div className="flex items-center gap-2">
            {rank === 1 && <span className="text-yellow-500 text-xl">👑</span>}
            <h3 className="font-bold text-lg">{pick.name}</h3>
          </div>
          <p className="text-gray-600 text-sm">{pick.team} • {pick.fixture}</p>
        </div>
        <div className="text-right">
          <p className="text-2xl font-bold text-blue-600">{pick.projected_pts.toFixed(1)}</p>
          <p className="text-xs text-gray-500">projected pts</p>
        </div>
      </div>
      <div className="mt-3 flex gap-4 text-sm">
        <span className="text-gray-600">Own: {pick.ownership}%</span>
        <span className="text-gray-600">Form: {pick.form}</span>
        <DifficultyBadge difficulty={pick.fixture_difficulty} />
      </div>
    </div>
  );
}

function TransferCard({ transfer, playerLookup }) {
  const outPlayer = playerLookup[transfer.out_id];
  return (
    <div className="p-4 rounded-lg border border-gray-200 bg-white">
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <p className="text-red-600 text-sm">OUT</p>
          <p className="font-medium">{outPlayer?.name || 'Unknown'}</p>
        </div>
        <div className="text-2xl">→</div>
        <div className="flex-1">
          <p className="text-green-600 text-sm">IN</p>
          <p className="font-medium">{transfer.in_name}</p>
          <p className="text-gray-500 text-sm">£{transfer.in_cost}m</p>
        </div>
        <div className="text-right">
          <p className="text-xl font-bold text-green-600">+{transfer.gain_4gw}</p>
          <p className="text-xs text-gray-500">pts over 4GW</p>
        </div>
      </div>
      {transfer.worth_hit && (
        <div className="mt-2 px-2 py-1 bg-orange-100 text-orange-800 rounded text-sm">
          ⚡ Worth a hit (-4)
        </div>
      )}
    </div>
  );
}

function SquadView({ squad, projections }) {
  const positions = [
    { pos: 1, label: 'Goalkeepers', count: 2 },
    { pos: 2, label: 'Defenders', count: 5 },
    { pos: 3, label: 'Midfielders', count: 5 },
    { pos: 4, label: 'Forwards', count: 3 },
  ];

  return (
    <div className="space-y-4">
      {positions.map(({ pos, label }) => (
        <div key={pos}>
          <h4 className="font-medium text-gray-700 mb-2">{label}</h4>
          <div className="grid gap-2">
            {squad
              .filter(p => p.position === pos)
              .sort((a, b) => b.projected_pts - a.projected_pts)
              .map(player => (
                <div 
                  key={player.player_id}
                  className={`p-3 rounded flex justify-between items-center ${
                    player.multiplier === 0 ? 'bg-gray-100 opacity-60' : 'bg-white border'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className={`w-8 h-8 rounded-full ${POS_COLORS[pos]} text-white text-xs flex items-center justify-center`}>
                      {POS_LABELS[pos]}
                    </span>
                    <div>
                      <p className="font-medium">
                        {player.name}
                        {player.is_captain && ' ©'}
                        {player.is_vice && ' (V)'}
                      </p>
                      {player.multiplier === 0 && (
                        <p className="text-xs text-gray-500">Bench</p>
                      )}
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-bold">{player.projected_pts.toFixed(1)}</p>
                    <p className="text-xs text-gray-500">{player.projected_4gw.toFixed(1)} (4GW)</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function TopPlayersTable({ players, title }) {
  return (
    <div>
      <h3 className="font-bold text-lg mb-3">{title}</h3>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b">
              <th className="text-left py-2">Player</th>
              <th className="text-left py-2">Team</th>
              <th className="text-right py-2">Price</th>
              <th className="text-right py-2">Own%</th>
              <th className="text-right py-2">Next GW</th>
              <th className="text-right py-2">4GW</th>
              <th className="text-left py-2">Fixture</th>
            </tr>
          </thead>
          <tbody>
            {players.slice(0, 10).map((p, i) => (
              <tr key={p.player_id} className={i % 2 === 0 ? 'bg-gray-50' : ''}>
                <td className="py-2 font-medium">{p.name}</td>
                <td className="py-2">{p.team}</td>
                <td className="py-2 text-right">£{p.price}m</td>
                <td className="py-2 text-right">{p.ownership}%</td>
                <td className="py-2 text-right font-bold">{p.next_gw_pts.toFixed(1)}</td>
                <td className="py-2 text-right">{p.next_4gw_pts.toFixed(1)}</td>
                <td className="py-2">{p.next_fixture}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ChipAlert({ chip }) {
  const icon = chip.type === 'double' ? '📈' : '⚠️';
  const bgColor = chip.type === 'double' ? 'bg-green-50 border-green-200' : 'bg-yellow-50 border-yellow-200';
  
  return (
    <div className={`p-4 rounded-lg border ${bgColor}`}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>
        <div>
          <h4 className="font-bold">GW{chip.gameweek}: {chip.type === 'double' ? 'Double Gameweek' : 'Blank Gameweek'}</h4>
          <p className="text-sm text-gray-700">{chip.notes}</p>
          <p className="text-sm font-medium mt-1">💡 {chip.chip_suggestion}</p>
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

  useEffect(() => {
    Promise.all([
      fetch('/data/recommendations.json').then(r => r.json()).catch(() => null),
      fetch('/data/my_team.json').then(r => r.json()).catch(() => null),
      fetch('/data/projections.json').then(r => r.json()).catch(() => null),
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
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading projections...</p>
        </div>
      </div>
    );
  }

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'squad', label: 'My Squad' },
    { id: 'players', label: 'Top Players' },
  ];

  // Build player lookup from squad
  const playerLookup = {};
  if (myTeam?.squad) {
    myTeam.squad.forEach(p => {
      playerLookup[p.player_id] = p;
    });
  }

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-gradient-to-r from-purple-700 to-blue-600 text-white p-6">
        <h1 className="text-2xl font-bold">FPL Brain</h1>
        <p className="text-purple-200">
          GW{recommendations?.next_gameweek || '?'} • Updated {recommendations?.generated_at ? new Date(recommendations.generated_at).toLocaleString() : 'N/A'}
        </p>
      </header>

      <nav className="bg-white border-b sticky top-0 z-10">
        <div className="flex">
          {tabs.map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-6 py-3 font-medium transition-colors ${
                activeTab === tab.id 
                  ? 'text-blue-600 border-b-2 border-blue-600' 
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
            {/* Captain Picks */}
            <section>
              <h2 className="text-xl font-bold mb-4">Captain Picks</h2>
              <div className="space-y-3">
                {recommendations?.captain_picks?.map((pick, i) => (
                  <CaptainCard key={pick.player_id} pick={pick} rank={i + 1} />
                ))}
                {!recommendations?.captain_picks?.length && (
                  <p className="text-gray-500">No captain data available</p>
                )}
              </div>
            </section>

            {/* Transfer Recommendations */}
            <section>
              <h2 className="text-xl font-bold mb-4">Transfer Recommendations</h2>
              <div className="space-y-3">
                {recommendations?.transfer_recommendations?.map((transfer, i) => (
                  <TransferCard key={i} transfer={transfer} playerLookup={playerLookup} />
                ))}
                {!recommendations?.transfer_recommendations?.length && (
                  <p className="text-gray-500 bg-white p-4 rounded-lg">
                    No transfers recommended - your squad looks strong! 💪
                  </p>
                )}
              </div>
            </section>

            {/* Chip Analysis */}
            {recommendations?.chip_analysis?.length > 0 && (
              <section>
                <h2 className="text-xl font-bold mb-4">Upcoming Chip Opportunities</h2>
                <div className="space-y-3">
                  {recommendations.chip_analysis.map((chip, i) => (
                    <ChipAlert key={i} chip={chip} />
                  ))}
                </div>
              </section>
            )}

            {/* Projected Points */}
            {myTeam && (
              <section className="bg-white rounded-lg p-4 border">
                <h2 className="text-lg font-bold mb-2">GW{recommendations?.next_gameweek} Projected Total</h2>
                <p className="text-4xl font-bold text-blue-600">{myTeam.total_projected_pts?.toFixed(1)} pts</p>
                <p className="text-sm text-gray-500 mt-1">Bank: £{myTeam.bank?.toFixed(1)}m</p>
              </section>
            )}
          </>
        )}

        {activeTab === 'squad' && myTeam && (
          <section>
            <h2 className="text-xl font-bold mb-4">My Squad</h2>
            <SquadView squad={myTeam.squad} projections={projections} />
          </section>
        )}

        {activeTab === 'players' && projections?.top_by_position && (
          <section className="space-y-8">
            {['FWD', 'MID', 'DEF', 'GK'].map(pos => (
              <TopPlayersTable 
                key={pos} 
                players={projections.top_by_position[pos] || []} 
                title={`Top ${pos}s`}
              />
            ))}
          </section>
        )}
      </main>

      <footer className="text-center py-6 text-gray-500 text-sm">
        Built for top 100 glory • Data updates daily at 6am UTC
      </footer>
    </div>
  );
}
