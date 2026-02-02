import { useState, useEffect } from 'react';

const POS_LABELS = { 1: 'GK', 2: 'DEF', 3: 'MID', 4: 'FWD' };
const POS_COLORS = { 1: 'bg-yellow-500', 2: 'bg-green-500', 3: 'bg-blue-500', 4: 'bg-red-500' };
const POS_COLORS_BY_NAME = { GK: 'bg-yellow-500', DEF: 'bg-green-500', MID: 'bg-blue-500', FWD: 'bg-red-500' };

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

function XminBar({ xmin }) {
  const pct = Math.min(100, (xmin / 90) * 100);
  const color = xmin >= 80 ? 'bg-green-400' : xmin >= 60 ? 'bg-yellow-400' : 'bg-red-400';
  return (
    <div className="w-12 h-1.5 bg-gray-200 rounded-full overflow-hidden" title={`${xmin} xMin`}>
      <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
    </div>
  );
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
    'low_xmin': 'bg-red-100 text-red-700',
    'rotation_risk': 'bg-yellow-100 text-yellow-700',
    'nailed': 'bg-green-100 text-green-700',
    'easy_next_2': 'bg-green-100 text-green-700',
  };
  const labelMap = {
    'hot_form': '🔥 Hot', 'cold_form': '🥶 Cold', 'easy_fixtures': '📅 Easy run',
    'hard_fixtures': '📅 Hard run', 'injury_doubt': '🏥 Injury', 'low_projection': '📉 Low pts',
    'low_xmin': '⏱️ Low mins', 'rotation_risk': '🔄 Rotation', 'nailed': '🔒 Nailed',
    'easy_next_2': '📅 Easy 2GW', 'mins_declining': '📉 Mins dropping', 'low_mins_played': '⏱️ Few mins',
  };
  return (
    <div className="flex flex-wrap gap-1">
      {reasons?.map((r, i) => {
        const isDGW = r.startsWith('dgw');
        const isBGW = r.startsWith('blank');
        if (isDGW) return <span key={i} className="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700 font-medium">🎯 {r.toUpperCase()}</span>;
        if (isBGW) return <span key={i} className="px-1.5 py-0.5 text-xs rounded bg-yellow-100 text-yellow-700">⚠️ {r}</span>;
        return <span key={i} className={`px-1.5 py-0.5 text-xs rounded ${colorMap[r] || 'bg-gray-100 text-gray-600'}`}>{labelMap[r] || r}</span>;
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
            {pick.is_template && <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded-full">Template</span>}
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
        {pick.estimated_captain_pct > 0 && <span className="text-gray-500">Est Cap: {pick.estimated_captain_pct}%</span>}
        <DifficultyBadge difficulty={pick.fixture_difficulty} />
      </div>
    </div>
  );
}

function AlternativeOption({ alt, tier, onTry }) {
  const tierColors = {
    budget: 'bg-blue-50 border-blue-200 text-blue-700',
    value: 'bg-green-50 border-green-200 text-green-700',
    premium: 'bg-purple-50 border-purple-200 text-purple-700',
  };
  const tierLabels = { budget: '💰 Budget', value: '⚖️ Value', premium: '👑 Premium' };

  if (!alt) return null;

  return (
    <div className={`flex items-center justify-between p-2 rounded-lg border ${tierColors[tier]}`}>
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium opacity-70">{tierLabels[tier]}</span>
        <span className="font-semibold">{alt.name}</span>
        <span className="text-sm opacity-70">£{alt.cost}m</span>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-bold">+{alt.gain_4gw}</span>
        <button
          onClick={() => onTry(alt)}
          className="px-2 py-1 bg-white/50 hover:bg-white rounded text-xs font-medium transition-colors"
        >
          Try
        </button>
      </div>
    </div>
  );
}

function TransferCard({ transfer, onTryTransfer, isApplied, onRemove, priority = 1 }) {
  const [showAlternatives, setShowAlternatives] = useState(false);
  const hasAlternatives = transfer.alternatives && (
    transfer.alternatives.budget || transfer.alternatives.value || transfer.alternatives.premium
  );

  const handleTryAlternative = (alt) => {
    // Create a modified transfer object with the alternative player
    const altTransfer = {
      ...transfer,
      in_id: alt.player_id,
      in_name: alt.name,
      in_cost: alt.cost,
      gain_4gw: alt.gain_4gw,
      value_score: alt.value_score,
    };
    onTryTransfer(altTransfer);
  };

  return (
    <div className={`rounded-lg border-2 transition-shadow ${isApplied ? 'border-green-400 bg-green-50' : 'border-gray-200 bg-white hover:shadow-md'}`}>
      <div className="p-4">
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
              {transfer.in_xmin && (
                <span className={`text-xs px-1.5 py-0.5 rounded ${
                  transfer.in_xmin >= 80 ? 'bg-green-100 text-green-700' :
                  transfer.in_xmin >= 60 ? 'bg-yellow-100 text-yellow-700' :
                  'bg-red-100 text-red-700'
                }`}>{transfer.in_xmin} xMin</span>
              )}
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
          <div className="flex items-center gap-2">
            {transfer.worth_hit && priority > 1 && (
              <span className="px-2 py-1 bg-orange-100 text-orange-700 rounded text-xs font-medium">
                ⚡ Worth -4 (net +{transfer.hit_value})
              </span>
            )}
            {hasAlternatives && !isApplied && (
              <button
                onClick={() => setShowAlternatives(!showAlternatives)}
                className="px-2 py-1 bg-gray-100 text-gray-600 rounded text-xs font-medium hover:bg-gray-200 transition-colors"
              >
                {showAlternatives ? '▲ Hide' : '▼ Alts'}
              </button>
            )}
            {isApplied ? (
              <button
                onClick={() => onRemove(transfer)}
                className="px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 transition-colors"
              >
                ✕ Remove
              </button>
            ) : (
              <button
                onClick={() => onTryTransfer(transfer)}
                className="px-3 py-1.5 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors"
              >
                Try This →
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Alternatives Section */}
      {showAlternatives && hasAlternatives && (
        <div className="border-t border-gray-200 bg-gray-50 p-3 space-y-2">
          <p className="text-xs text-gray-500 font-medium uppercase tracking-wide">Alternative Options</p>
          {transfer.alternatives.budget && (
            <AlternativeOption alt={transfer.alternatives.budget} tier="budget" onTry={handleTryAlternative} />
          )}
          {transfer.alternatives.value && (
            <AlternativeOption alt={transfer.alternatives.value} tier="value" onTry={handleTryAlternative} />
          )}
          {transfer.alternatives.premium && (
            <AlternativeOption alt={transfer.alternatives.premium} tier="premium" onTry={handleTryAlternative} />
          )}
        </div>
      )}
    </div>
  );
}

function ChipCard({ chip }) {
  const colors = { 'Bench Boost': 'from-green-500 to-emerald-600', 'Triple Captain': 'from-purple-500 to-indigo-600', 'Free Hit': 'from-orange-500 to-red-500', 'Wildcard': 'from-blue-500 to-cyan-600' };
  const icons = { 'Bench Boost': '🪑', 'Triple Captain': '👑', 'Free Hit': '⚡', 'Wildcard': '🃏' };
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
          <span className={`px-3 py-1 rounded-full text-sm font-medium ${chip.confidence === 'HIGH' ? 'bg-white/30' : 'bg-white/20'}`}>{chip.confidence}</span>
        </div>
        {chip.recommended_player && <p className="mt-2 text-white/90 text-sm">Player: <strong>{chip.recommended_player}</strong></p>}
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
          {starters.sort((a, b) => a.position - b.position || b.projected_pts - a.projected_pts).map(player => (
            <div key={player.player_id} className="p-3 rounded-lg bg-white border flex justify-between items-center">
              <div className="flex items-center gap-3">
                <span className={`w-10 h-10 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center font-medium`}>{POS_LABELS[player.position]}</span>
                <div>
                  <div className="flex items-center gap-1">
                    <p className="font-medium">{player.name}{player.is_captain && <span className="ml-1 text-yellow-600">(C)</span>}{player.is_vice && <span className="ml-1 text-gray-400">(V)</span>}</p>
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
                <span className={`w-8 h-8 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center`}>{POS_LABELS[player.position]}</span>
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

// ===================== NEW: STARTING XI COMPONENTS =====================

function XIPlayerCard({ player, isCaptain, isVice }) {
  const isNew = player.isNew;
  return (
    <div className={`relative flex flex-col items-center p-2 rounded-lg border-2 ${isNew ? 'bg-green-50 border-green-400' : 'bg-white'} ${isCaptain ? 'border-yellow-400 shadow-md' : isVice ? 'border-gray-400' : isNew ? 'border-green-400' : 'border-gray-200'}`}>
      {isCaptain && <span className="absolute -top-2 -right-2 w-6 h-6 bg-yellow-400 text-black text-xs font-bold rounded-full flex items-center justify-center shadow">C</span>}
      {isVice && !isCaptain && <span className="absolute -top-2 -right-2 w-5 h-5 bg-gray-400 text-white text-xs font-bold rounded-full flex items-center justify-center">V</span>}
      {isNew && <span className="absolute -top-2 -left-2 px-1.5 py-0.5 bg-green-500 text-white text-xs font-bold rounded shadow">NEW</span>}
      <span className={`text-xs px-1.5 py-0.5 rounded ${POS_COLORS_BY_NAME[player.position]} text-white font-medium`}>{player.position}</span>
      <span className="text-sm font-semibold text-gray-800 mt-1 truncate max-w-20 text-center">{player.name}</span>
      <span className="text-xs text-gray-500">{player.team}</span>
      <span className={`text-lg font-bold ${isNew ? 'text-green-700' : 'text-green-600'}`}>{player.effective_pts?.toFixed(1)}</span>
      <div className="flex items-center gap-1 mt-1">
        <XminBar xmin={player.xmin} />
        <span className="text-xs text-gray-400">{player.xmin}</span>
      </div>
      <div className="mt-1">
        <span className={`text-xs px-1.5 py-0.5 rounded ${
          player.is_dgw ? 'bg-purple-100 text-purple-700 font-medium' :
          player.difficulty < 0.85 ? 'bg-green-100 text-green-700' :
          player.difficulty > 1.15 ? 'bg-red-100 text-red-700' : 'bg-gray-100 text-gray-600'
        }`}>{player.is_dgw ? 'DGW' : player.fixture?.split(' ')[0] || '?'}</span>
      </div>
    </div>
  );
}

function PitchFormation({ xi, captain, viceCapt }) {
  const grouped = { GK: [], DEF: [], MID: [], FWD: [] };
  xi?.forEach(p => grouped[p.position]?.push(p));
  return (
    <div className="bg-gradient-to-b from-green-600 to-green-700 rounded-xl p-4 space-y-2">
      {['GK', 'DEF', 'MID', 'FWD'].map(pos => (
        <div key={pos} className="flex justify-center gap-2 flex-wrap">
          {grouped[pos].map((p, i) => (
            <XIPlayerCard key={`${p.name}-${i}`} player={p} isCaptain={captain?.name === p.name} isVice={viceCapt?.name === p.name} />
          ))}
        </div>
      ))}
    </div>
  );
}

function BenchRow({ bench }) {
  return (
    <div className="mt-3 p-3 bg-gray-100 rounded-lg">
      <div className="text-xs text-gray-500 mb-2 font-medium uppercase tracking-wide">Bench (auto-sub order)</div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {bench?.map((p, i) => (
          <div key={p.name} className={`flex-shrink-0 flex items-center gap-2 rounded-lg px-3 py-2 border ${p.isNew ? 'bg-green-50 border-green-400' : p.status === 'blank' ? 'border-yellow-400 bg-yellow-50' : p.status === 'unlikely' ? 'border-red-300 bg-red-50' : 'bg-white border-gray-200'}`}>
            <span className="text-xs text-gray-400 font-mono w-4">{p.bench_order}</span>
            <span className={`text-xs px-1 py-0.5 rounded ${POS_COLORS_BY_NAME[p.position]} text-white`}>{p.position}</span>
            <span className="text-sm text-gray-700">{p.name}</span>
            {p.isNew && <span className="px-1 py-0.5 bg-green-500 text-white text-xs rounded font-medium">NEW</span>}
            <span className={`text-sm font-semibold ${p.isNew ? 'text-green-700' : 'text-green-600'}`}>{p.effective_pts?.toFixed(1)}</span>
            <XminBar xmin={p.xmin} />
            {p.status === 'blank' && <span className="text-xs text-yellow-600">BGW</span>}
            {p.status === 'unlikely' && <span className="text-xs text-red-500">Low xMin</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

function GWSelector({ gws, selected, onChange }) {
  return (
    <div className="flex gap-1 bg-gray-100 p-1 rounded-lg">
      {gws.map(gw => (
        <button key={gw} onClick={() => onChange(gw)} className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${selected === gw ? 'bg-purple-600 text-white shadow' : 'text-gray-600 hover:text-gray-900 hover:bg-white'}`}>
          GW{gw}
        </button>
      ))}
    </div>
  );
}

function StartingXIView({ data, plannedTransfers = [], projections }) {
  const [selectedGW, setSelectedGW] = useState(null);
  const [viewMode, setViewMode] = useState('current'); // 'current' or 'planned'

  useEffect(() => {
    if (data?.recommendations?.length && !selectedGW) {
      setSelectedGW(data.recommendations[0]?.gameweek);
    }
  }, [data, selectedGW]);

  // Auto-switch to planned view when transfers are added
  useEffect(() => {
    if (plannedTransfers.length > 0 && viewMode === 'current') {
      setViewMode('planned');
    }
  }, [plannedTransfers.length]);

  if (!data?.recommendations?.length) {
    return <div className="bg-white p-6 rounded-lg border text-center text-gray-500">No Starting XI data available yet.</div>;
  }

  const gws = data.recommendations.map(r => r.gameweek);
  const currentData = data.recommendations.find(r => r.gameweek === selectedGW);

  if (!currentData) return null;

  // Recalculate optimal XI with planned transfers
  const calculateOptimalXI = () => {
    if (!plannedTransfers.length || viewMode === 'current') {
      return {
        xi: currentData.starting_xi.map(p => ({ ...p, isNew: false })),
        bench: currentData.bench.map(p => ({ ...p, isNew: false })),
      };
    }

    // Combine all players (XI + bench)
    const allSquadPlayers = [...currentData.starting_xi, ...currentData.bench];
    const allProjections = Object.values(projections?.top_by_position || {}).flat();

    // Apply transfers to get new squad
    const newSquad = allSquadPlayers.map(player => {
      const transfer = plannedTransfers.find(t => t.out_name === player.name);
      if (transfer) {
        const incomingPlayer = allProjections.find(p => p.player_id === transfer.in_id);
        if (incomingPlayer) {
          const gwFixture = incomingPlayer.fixture_preview?.find(f => f.gw === selectedGW);
          return {
            ...player,
            name: transfer.in_name,
            team: incomingPlayer.team,
            effective_pts: (incomingPlayer.next_gw_pts || 0) * 0.9,
            projected_pts: incomingPlayer.next_gw_pts || 0,
            xmin: 80,
            fixture: gwFixture?.fixture || incomingPlayer.next_fixture,
            difficulty: gwFixture?.difficulty || incomingPlayer.next_fixture_diff,
            is_dgw: gwFixture?.is_dgw || false,
            isNew: true,
          };
        }
      }
      return { ...player, isNew: false };
    });

    // Group by position
    const byPosition = { GK: [], DEF: [], MID: [], FWD: [] };
    newSquad.forEach(p => byPosition[p.position]?.push(p));

    // Sort each position by effective_pts
    Object.keys(byPosition).forEach(pos => {
      byPosition[pos].sort((a, b) => (b.effective_pts || 0) - (a.effective_pts || 0));
    });

    // Select optimal XI respecting formation rules (1 GK, 3-5 DEF, 2-5 MID, 1-3 FWD)
    const xi = [];
    const bench = [];

    // Always 1 GK
    xi.push(byPosition.GK[0]);
    if (byPosition.GK[1]) bench.push(byPosition.GK[1]);

    // Find best formation by trying common ones
    const formations = [
      { def: 3, mid: 5, fwd: 2 },
      { def: 3, mid: 4, fwd: 3 },
      { def: 4, mid: 4, fwd: 2 },
      { def: 4, mid: 3, fwd: 3 },
      { def: 5, mid: 3, fwd: 2 },
      { def: 5, mid: 4, fwd: 1 },
    ];

    let bestFormation = formations[0];
    let bestTotal = 0;

    formations.forEach(f => {
      if (byPosition.DEF.length >= f.def && byPosition.MID.length >= f.mid && byPosition.FWD.length >= f.fwd) {
        const total =
          byPosition.DEF.slice(0, f.def).reduce((s, p) => s + (p.effective_pts || 0), 0) +
          byPosition.MID.slice(0, f.mid).reduce((s, p) => s + (p.effective_pts || 0), 0) +
          byPosition.FWD.slice(0, f.fwd).reduce((s, p) => s + (p.effective_pts || 0), 0);
        if (total > bestTotal) {
          bestTotal = total;
          bestFormation = f;
        }
      }
    });

    // Build XI with best formation
    xi.push(...byPosition.DEF.slice(0, bestFormation.def));
    xi.push(...byPosition.MID.slice(0, bestFormation.mid));
    xi.push(...byPosition.FWD.slice(0, bestFormation.fwd));

    // Remaining go to bench
    bench.push(...byPosition.DEF.slice(bestFormation.def));
    bench.push(...byPosition.MID.slice(bestFormation.mid));
    bench.push(...byPosition.FWD.slice(bestFormation.fwd));

    // Sort bench by effective_pts and assign bench_order
    bench.sort((a, b) => (b.effective_pts || 0) - (a.effective_pts || 0));
    bench.forEach((p, i) => p.bench_order = i + 1);

    return { xi, bench };
  };

  const { xi: displayXI, bench: displayBench } = calculateOptimalXI();

  // Calculate totals
  const currentTotal = currentData.total_effective_pts;
  const plannedTotal = displayXI.reduce((sum, p) => sum + (p.effective_pts || 0), 0);
  const ptsDiff = plannedTotal - currentTotal;

  // Best captain = highest effective_pts in XI
  const sortedByPts = [...displayXI].sort((a, b) => (b.effective_pts || 0) - (a.effective_pts || 0));
  const displayCaptain = sortedByPts[0] || displayXI[0];
  const displayVice = sortedByPts[1] || displayXI[1];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold">📋 Starting XI</h2>
        <div className="flex items-center gap-3">
          {plannedTransfers.length > 0 && (
            <div className="flex bg-gray-100 p-1 rounded-lg">
              <button
                onClick={() => setViewMode('current')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'current' ? 'bg-white shadow text-gray-800' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Current
              </button>
              <button
                onClick={() => setViewMode('planned')}
                className={`px-3 py-1.5 rounded-md text-sm font-medium transition-colors ${viewMode === 'planned' ? 'bg-green-500 text-white shadow' : 'text-gray-600 hover:text-gray-900'}`}
              >
                Planned ✨
              </button>
            </div>
          )}
          <GWSelector gws={gws} selected={selectedGW} onChange={setSelectedGW} />
        </div>
      </div>

      {plannedTransfers.length > 0 && viewMode === 'planned' && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-lg text-green-800 text-sm flex items-center justify-between">
          <span>
            🔄 Showing XI with {plannedTransfers.length} planned transfer{plannedTransfers.length > 1 ? 's' : ''} applied
          </span>
          <span className={`font-bold ${ptsDiff >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {ptsDiff >= 0 ? '+' : ''}{ptsDiff.toFixed(1)} eff pts
          </span>
        </div>
      )}

      {currentData.alerts?.needs_attention && viewMode === 'current' && (
        <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-yellow-800 text-sm">
          ⚠️ GW{currentData.gameweek} needs attention: {currentData.alerts.blank_count > 0 && `${currentData.alerts.blank_count} players blanking`}
          {currentData.alerts.blank_count > 0 && currentData.alerts.low_xmin_count > 0 && ', '}
          {currentData.alerts.low_xmin_count > 0 && `${currentData.alerts.low_xmin_count} with low xMin`}
        </div>
      )}

      <div className={`flex items-center justify-between p-4 rounded-lg border ${viewMode === 'planned' && plannedTransfers.length > 0 ? 'bg-green-50 border-green-200' : 'bg-white'}`}>
        <div className="flex items-center gap-4">
          <span className="text-3xl font-bold text-gray-800">{currentData.formation}</span>
          <span className="text-sm text-gray-500">Formation</span>
        </div>
        <div className="text-right">
          <span className={`text-3xl font-bold ${viewMode === 'planned' && plannedTransfers.length > 0 ? 'text-green-600' : 'text-green-600'}`}>
            {viewMode === 'planned' ? plannedTotal.toFixed(1) : currentTotal}
          </span>
          <span className="text-sm text-gray-500 ml-1">eff pts</span>
        </div>
      </div>

      <PitchFormation xi={displayXI} captain={displayCaptain} viceCapt={displayVice} />
      <BenchRow bench={displayBench} />

      <div className="p-4 bg-gray-50 rounded-lg text-sm text-gray-600">
        <div className="font-medium text-gray-700 mb-2">Legend</div>
        <div className="flex flex-wrap gap-4">
          <div className="flex items-center gap-2"><div className="w-6 h-1.5 bg-green-400 rounded-full" /><span>xMin ≥80</span></div>
          <div className="flex items-center gap-2"><div className="w-6 h-1.5 bg-yellow-400 rounded-full" /><span>xMin 60-79</span></div>
          <div className="flex items-center gap-2"><div className="w-6 h-1.5 bg-red-400 rounded-full" /><span>xMin &lt;60</span></div>
        </div>
        <p className="mt-2 text-xs text-gray-500">
          <strong>Effective pts</strong> = projected pts × (xMin/90). Accounts for rotation risk and availability.
        </p>
      </div>
    </div>
  );
}

// ===================== END STARTING XI COMPONENTS =====================

// ===================== SQUAD PLANNER COMPONENTS =====================

function SquadPlannerView({ currentSquad, plannedTransfers, projections, onRemoveTransfer, onClearAll }) {
  // Build the planned squad by applying transfers
  const plannedSquad = currentSquad?.map(player => {
    const transferOut = plannedTransfers.find(t => t.out_id === player.player_id);
    if (transferOut) {
      // Find the incoming player's projection data
      const incomingProj = Object.values(projections?.top_by_position || {})
        .flat()
        .find(p => p.player_id === transferOut.in_id);

      if (incomingProj) {
        return {
          ...player,
          player_id: transferOut.in_id,
          name: transferOut.in_name,
          projected_pts: incomingProj.next_gw_pts || 0,
          projected_4gw: incomingProj.next_4gw_pts || 0,
          form_trend: incomingProj.form_trend,
          fixture_preview: incomingProj.fixture_preview,
          isNew: true,
          transferCost: transferOut.in_cost,
        };
      }
    }
    return { ...player, isNew: false };
  }) || [];

  // Calculate totals
  const currentTotal = currentSquad?.reduce((sum, p) => sum + (p.multiplier > 0 ? (p.projected_pts || 0) : 0), 0) || 0;
  const plannedTotal = plannedSquad.reduce((sum, p) => sum + (p.multiplier > 0 ? (p.projected_pts || 0) : 0), 0);
  const currentTotal4GW = currentSquad?.reduce((sum, p) => sum + (p.multiplier > 0 ? (p.projected_4gw || 0) : 0), 0) || 0;
  const plannedTotal4GW = plannedSquad.reduce((sum, p) => sum + (p.multiplier > 0 ? (p.projected_4gw || 0) : 0), 0);

  const gwDiff = plannedTotal - currentTotal;
  const fourGWDiff = plannedTotal4GW - currentTotal4GW;
  const hitCost = plannedTransfers.length > 1 ? (plannedTransfers.length - 1) * 4 : 0;
  const netGain4GW = fourGWDiff - hitCost;

  if (plannedTransfers.length === 0) {
    return (
      <div className="bg-white p-8 rounded-lg border text-center">
        <p className="text-4xl mb-4">🔄</p>
        <h3 className="font-bold text-lg text-gray-800 mb-2">Squad Planner</h3>
        <p className="text-gray-600">Click "Try This" on any transfer recommendation to see how it affects your squad.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Summary Card */}
      <div className="bg-gradient-to-r from-purple-600 to-blue-600 rounded-xl p-6 text-white">
        <div className="flex justify-between items-start mb-4">
          <div>
            <p className="text-purple-200 text-sm">Planned Changes</p>
            <p className="text-2xl font-bold">{plannedTransfers.length} transfer{plannedTransfers.length > 1 ? 's' : ''}</p>
          </div>
          <button
            onClick={onClearAll}
            className="px-3 py-1.5 bg-white/20 hover:bg-white/30 rounded-lg text-sm font-medium transition-colors"
          >
            Clear All
          </button>
        </div>

        <div className="grid grid-cols-3 gap-4 text-center">
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-purple-200 text-xs">Next GW</p>
            <p className={`text-2xl font-bold ${gwDiff >= 0 ? 'text-green-300' : 'text-red-300'}`}>
              {gwDiff >= 0 ? '+' : ''}{gwDiff.toFixed(1)}
            </p>
            <p className="text-xs text-purple-200">pts</p>
          </div>
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-purple-200 text-xs">4GW Total</p>
            <p className={`text-2xl font-bold ${fourGWDiff >= 0 ? 'text-green-300' : 'text-red-300'}`}>
              {fourGWDiff >= 0 ? '+' : ''}{fourGWDiff.toFixed(1)}
            </p>
            <p className="text-xs text-purple-200">pts</p>
          </div>
          <div className="bg-white/10 rounded-lg p-3">
            <p className="text-purple-200 text-xs">Net Gain</p>
            <p className={`text-2xl font-bold ${netGain4GW >= 0 ? 'text-green-300' : 'text-red-300'}`}>
              {netGain4GW >= 0 ? '+' : ''}{netGain4GW.toFixed(1)}
            </p>
            <p className="text-xs text-purple-200">{hitCost > 0 ? `(-${hitCost} hit)` : 'pts'}</p>
          </div>
        </div>
      </div>

      {/* Applied Transfers */}
      <div className="bg-white rounded-lg border p-4">
        <h3 className="font-bold text-gray-700 mb-3">Applied Transfers</h3>
        <div className="space-y-2">
          {plannedTransfers.map((t, i) => (
            <div key={i} className="flex items-center justify-between p-3 bg-green-50 rounded-lg border border-green-200">
              <div className="flex items-center gap-3">
                <span className="text-red-500 font-medium">{t.out_name}</span>
                <span className="text-gray-400">→</span>
                <span className="text-green-600 font-medium">{t.in_name}</span>
                <span className="text-gray-500 text-sm">(£{t.in_cost}m)</span>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-green-600 font-bold">+{t.gain_4gw} pts/4GW</span>
                <button
                  onClick={() => onRemoveTransfer(t)}
                  className="text-red-500 hover:text-red-700 text-sm font-medium"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Side by Side Comparison */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Current Squad */}
        <div className="bg-white rounded-lg border">
          <div className="p-4 border-b bg-gray-50">
            <h3 className="font-bold text-gray-700">Current Squad</h3>
            <p className="text-sm text-gray-500">GW: {currentTotal.toFixed(1)} pts • 4GW: {currentTotal4GW.toFixed(1)} pts</p>
          </div>
          <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
            {currentSquad?.filter(p => p.multiplier > 0).sort((a, b) => a.position - b.position).map(player => {
              const isBeingReplaced = plannedTransfers.some(t => t.out_id === player.player_id);
              return (
                <div key={player.player_id} className={`flex items-center justify-between p-2 rounded ${isBeingReplaced ? 'bg-red-50 line-through opacity-60' : 'bg-gray-50'}`}>
                  <div className="flex items-center gap-2">
                    <span className={`w-8 h-8 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center`}>
                      {POS_LABELS[player.position]}
                    </span>
                    <span className="font-medium text-sm">{player.name}</span>
                  </div>
                  <span className="font-bold text-gray-700">{player.projected_pts?.toFixed(1)}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Planned Squad */}
        <div className="bg-white rounded-lg border border-green-200">
          <div className="p-4 border-b bg-green-50">
            <h3 className="font-bold text-green-700">Planned Squad</h3>
            <p className="text-sm text-green-600">GW: {plannedTotal.toFixed(1)} pts • 4GW: {plannedTotal4GW.toFixed(1)} pts</p>
          </div>
          <div className="p-4 space-y-2 max-h-96 overflow-y-auto">
            {plannedSquad?.filter(p => p.multiplier > 0).sort((a, b) => a.position - b.position).map(player => (
              <div key={player.player_id} className={`flex items-center justify-between p-2 rounded ${player.isNew ? 'bg-green-100 border border-green-300' : 'bg-gray-50'}`}>
                <div className="flex items-center gap-2">
                  <span className={`w-8 h-8 rounded-full ${POS_COLORS[player.position]} text-white text-xs flex items-center justify-center`}>
                    {POS_LABELS[player.position]}
                  </span>
                  <span className="font-medium text-sm">{player.name}</span>
                  {player.isNew && <span className="px-1.5 py-0.5 bg-green-500 text-white text-xs rounded">NEW</span>}
                </div>
                <span className={`font-bold ${player.isNew ? 'text-green-700' : 'text-gray-700'}`}>{player.projected_pts?.toFixed(1)}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ===================== END SQUAD PLANNER COMPONENTS =====================

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
                <td className="py-3 px-4"><FixtureRun fixtures={p.fixture_preview} /></td>
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
  const [startingXI, setStartingXI] = useState(null);
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(true);

  // Squad Planner state
  const [plannedTransfers, setPlannedTransfers] = useState([]);
  const [showPlanner, setShowPlanner] = useState(false);

  useEffect(() => {
    Promise.all([
      fetch('/data/recommendations.json').then(r => r.ok ? r.json() : null),
      fetch('/data/my_team.json').then(r => r.ok ? r.json() : null),
      fetch('/data/projections.json').then(r => r.ok ? r.json() : null),
      fetch('/data/starting_xi.json').then(r => r.ok ? r.json() : null),
    ]).then(([recs, team, proj, xi]) => {
      setRecommendations(recs);
      setMyTeam(team);
      setProjections(proj);
      setStartingXI(xi);
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

  // Squad Planner functions
  const handleTryTransfer = (transfer) => {
    // Check if this transfer is already applied
    if (plannedTransfers.some(t => t.out_id === transfer.out_id)) {
      return; // Already applied
    }
    // Check if the outgoing player is already being transferred out
    if (plannedTransfers.some(t => t.in_id === transfer.out_id)) {
      return; // Can't transfer out a player we're bringing in
    }
    setPlannedTransfers([...plannedTransfers, transfer]);
    setShowPlanner(true);
  };

  const handleRemoveTransfer = (transfer) => {
    setPlannedTransfers(plannedTransfers.filter(t => t.out_id !== transfer.out_id));
  };

  const handleClearAllTransfers = () => {
    setPlannedTransfers([]);
  };

  const tabs = [
    { id: 'overview', label: '🎯 Overview' },
    { id: 'planner', label: `🔄 Planner${plannedTransfers.length > 0 ? ` (${plannedTransfers.length})` : ''}` },
    { id: 'xi', label: '📋 Starting XI' },
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
              <><span>•</span><span className="text-yellow-300">DGWs: {recommendations.fixture_alerts.dgw_gws.join(', ')}</span></>
            )}
          </div>
        </div>
      </header>

      <nav className="bg-white border-b sticky top-0 z-10 shadow-sm">
        <div className="max-w-4xl mx-auto flex overflow-x-auto">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={`px-5 py-4 font-medium whitespace-nowrap transition-all ${activeTab === tab.id ? 'text-purple-600 border-b-2 border-purple-600 bg-purple-50' : 'text-gray-600 hover:text-gray-900'}`}>
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
              {plannedTransfers.length > 0 && (
                <div className="mb-4 p-3 rounded-lg bg-green-50 border border-green-200 text-green-800 text-sm">
                  <span className="font-medium">🔄 With planned transfers:</span> Check if incoming players could be better captain options below.
                </div>
              )}
              {recommendations?.captain_picks?.differential_pick && (
                <div className="mb-4 p-4 rounded-lg bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-lg">🎯</span>
                    <h3 className="font-bold text-blue-800">Differential Option</h3>
                    <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${
                      recommendations.captain_picks.differential_pick.risk_level === 'low_risk' ? 'bg-green-100 text-green-700' :
                      recommendations.captain_picks.differential_pick.risk_level === 'medium_risk' ? 'bg-yellow-100 text-yellow-700' :
                      'bg-red-100 text-red-700'
                    }`}>{recommendations.captain_picks.differential_pick.risk_level?.replace('_', ' ')}</span>
                  </div>
                  <p className="text-sm text-gray-700">
                    <span className="font-semibold">{recommendations.captain_picks.differential_pick.name}</span>
                    {' '}({recommendations.captain_picks.differential_pick.ownership}% owned) vs safe pick:
                    {' '}<span className={recommendations.captain_picks.differential_pick.vs_safe_diff >= 0 ? 'text-green-600' : 'text-red-600'}>
                      {recommendations.captain_picks.differential_pick.vs_safe_diff >= 0 ? '+' : ''}{recommendations.captain_picks.differential_pick.vs_safe_diff} pts
                    </span>
                    {' '}• EO advantage: {recommendations.captain_picks.differential_pick.eo_advantage}%
                  </p>
                </div>
              )}
              <div className="space-y-3">
                {/* Show incoming players from transfers as potential captain options */}
                {plannedTransfers.map(transfer => {
                  const allPlayers = Object.values(projections?.top_by_position || {}).flat();
                  const incomingPlayer = allPlayers.find(p => p.player_id === transfer.in_id);
                  if (incomingPlayer && incomingPlayer.next_gw_pts >= 5) {
                    return (
                      <div key={`new-${transfer.in_id}`} className="p-4 rounded-lg border-2 border-green-400 bg-green-50">
                        <div className="flex justify-between items-start">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-0.5 bg-green-500 text-white text-xs rounded font-medium">NEW</span>
                              <h3 className="font-bold text-lg">{incomingPlayer.name}</h3>
                              {incomingPlayer.form_trend === 'hot' && <span className="text-orange-500">🔥</span>}
                            </div>
                            <p className="text-gray-600 text-sm">{incomingPlayer.team} • {incomingPlayer.next_fixture}</p>
                          </div>
                          <div className="text-right">
                            <p className="text-3xl font-bold text-green-600">{incomingPlayer.next_gw_pts?.toFixed(1)}</p>
                            <p className="text-sm text-gray-500">×2 = {(incomingPlayer.next_gw_pts * 2).toFixed(1)}</p>
                          </div>
                        </div>
                        <div className="mt-2 text-xs text-green-700">
                          Incoming from transfer - consider for captain if projected higher than current options
                        </div>
                      </div>
                    );
                  }
                  return null;
                })}
                {recommendations?.captain_picks?.picks?.map((pick, i) => <CaptainCard key={pick.player_id} pick={pick} rank={i + 1} />)}
              </div>
            </section>
            <section>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold">📈 Transfer Recommendations</h2>
                {plannedTransfers.length > 0 && (
                  <button
                    onClick={() => setActiveTab('planner')}
                    className="px-3 py-1.5 bg-purple-100 text-purple-700 rounded-lg text-sm font-medium hover:bg-purple-200 transition-colors"
                  >
                    View Planner ({plannedTransfers.length})
                  </button>
                )}
              </div>
              <div className="space-y-3">
                {recommendations?.transfer_recommendations?.length > 0 ? (
                  recommendations.transfer_recommendations.map((t, i) => (
                    <TransferCard
                      key={i}
                      transfer={t}
                      onTryTransfer={handleTryTransfer}
                      onRemove={handleRemoveTransfer}
                      isApplied={plannedTransfers.some(pt => pt.out_id === t.out_id)}
                      priority={t.priority || i + 1}
                    />
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

        {activeTab === 'planner' && (
          <SquadPlannerView
            currentSquad={myTeam?.squad}
            plannedTransfers={plannedTransfers}
            projections={projections}
            onRemoveTransfer={handleRemoveTransfer}
            onClearAll={handleClearAllTransfers}
          />
        )}

        {activeTab === 'xi' && <StartingXIView data={startingXI} plannedTransfers={plannedTransfers} projections={projections} />}

        {activeTab === 'chips' && (
          <section>
            <h2 className="text-xl font-bold mb-4">🎮 Chip Strategy</h2>
            {recommendations?.chip_strategy?.length > 0 ? (
              <div className="space-y-4">{recommendations.chip_strategy.map((chip, i) => <ChipCard key={i} chip={chip} />)}</div>
            ) : (
              <div className="bg-white p-6 rounded-lg border text-center"><p className="text-gray-600">No chip recommendations yet. Check back closer to DGWs/BGWs.</p></div>
            )}
            {myTeam?.chips_available && (
              <div className="mt-6 p-4 bg-gray-50 rounded-lg">
                <h3 className="font-medium text-gray-700 mb-2">Available Chips</h3>
                <div className="flex flex-wrap gap-2">{myTeam.chips_available.map(chip => <span key={chip} className="px-3 py-1 bg-white border rounded-full text-sm">{chip.replace('_', ' ')}</span>)}</div>
              </div>
            )}
          </section>
        )}

        {activeTab === 'squad' && myTeam && <SquadView squad={myTeam.squad} />}

        {activeTab === 'players' && projections?.top_by_position && (
          <div className="space-y-6">
            {['FWD', 'MID', 'DEF', 'GK'].map(pos => (
              <TopPlayersTable key={pos} players={projections.top_by_position[pos]} title={pos === 'GK' ? 'Goalkeepers' : pos === 'DEF' ? 'Defenders' : pos === 'MID' ? 'Midfielders' : 'Forwards'} />
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
