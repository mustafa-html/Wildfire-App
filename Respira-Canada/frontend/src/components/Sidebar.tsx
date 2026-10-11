import React, { useContext } from 'react';
import { FireRiskContext } from '../context/FireRiskContext';
import { ActiveFire, FireLocation, FireRiskStation, PlumeData } from '../types';
import { REGIONS, STAGE_COLORS } from '../utils/constants';
import {
  aqhiColor, fmt, formatTimestamp, nearestStationTo, riskColor, riskInfoForLevel, windCardinal,
} from '../utils/helpers';
import LoadingSpinner from './LoadingSpinner';

interface SidebarProps {
  onShowMission: () => void;
}

const Panel: React.FC<{ children: React.ReactNode; className?: string }> = ({ children, className = '' }) => (
  <div className={`rounded-lg bg-black/25 p-3 ${className}`}>{children}</div>
);

const Row: React.FC<{ label: string; value: React.ReactNode }> = ({ label, value }) => (
  <div className="flex justify-between gap-3 py-0.5">
    <span className="text-white/65">{label}</span>
    <span className="text-right font-medium">{value}</span>
  </div>
);

const LevelBadge: React.FC<{ level: FireRiskStation['risk_level'] }> = ({ level }) => (
  <span className="rounded px-2 py-0.5 text-sm font-semibold text-white" style={{ backgroundColor: riskColor(level) }}>
    {riskInfoForLevel(level)?.label ?? 'No FWI reported'}
  </span>
);

const SmokeSummary: React.FC<{ plume: PlumeData | null; error: string | null }> = ({ plume, error }) => {
  if (error) return <p className="text-sm text-red-300">{error}</p>;
  if (!plume) return <p className="text-sm text-white/60">Calculating smoke projection…</p>;
  const last = plume.frames[plume.frames.length - 1];
  if (!last) return <p className="text-sm text-white/60">No plume: the fire is too small or conditions too mild.</p>;
  const inputs = plume.inputs ?? {};
  const kmh = inputs.wind_speed_m_s != null ? inputs.wind_speed_m_s * 3.6 : null;
  return (
    <Panel>
      <Row label={`Reach after ${last.hours} h`} value={fmt(last.meta.plume_length_m / 1000, 0, ' km')} />
      <Row label="Wind" value={`${fmt(kmh, 0, ' km/h')} from ${windCardinal(inputs.wind_dir_from)}`} />
      <p className="mt-1 text-xs text-white/50">Wind: {inputs.wind_source ?? '—'}. Rough visual estimate, not a dispersion forecast.</p>
    </Panel>
  );
};

const StationDetails: React.FC<{ s: FireRiskStation }> = ({ s }) => {
  const w = s.weather_conditions ?? {};
  const f = s.fire_indices ?? {};
  return (
    <>
      <Panel className="mb-3">
        <div className="mb-1 flex items-center justify-between">
          <span className="text-sm text-white/70">Fire danger</span>
          <LevelBadge level={s.risk_level} />
        </div>
        <div className="text-3xl font-bold">FWI {fmt(f.fwi, 1)}</div>
        <p className="mt-1 text-sm text-white/75">{s.interpretation}</p>
      </Panel>
      <h3 className="mb-1 text-sm font-semibold text-white/90">Noon weather</h3>
      <Panel className="mb-3 text-sm">
        <Row label="Temperature" value={fmt(w.temperature, 1, ' °C')} />
        <Row label="Humidity" value={fmt(w.relative_humidity, 0, '%')} />
        <Row label="Wind" value={`${fmt(w.wind_speed, 0, ' km/h')} ${windCardinal(w.wind_direction)}`} />
        <Row label="Rain (24 h)" value={fmt(w.precip_24h, 1, ' mm')} />
      </Panel>
      <h3 className="mb-1 text-sm font-semibold text-white/90">Fire Weather Index System</h3>
      <Panel className="mb-3 grid grid-cols-3 gap-2 text-center text-sm">
        {([['FFMC', f.ffmc, 1], ['DMC', f.dmc, 1], ['DC', f.dc, 0], ['ISI', f.isi, 1], ['BUI', f.bui, 1], ['FWI', f.fwi, 1]] as const)
          .map(([k, v, d]) => (
            <div key={k}>
              <div className="text-xs text-white/60">{k}</div>
              <div className="font-semibold">{fmt(v, d)}</div>
            </div>
          ))}
      </Panel>
      <p className="mb-3 text-xs text-white/50">Observed {formatTimestamp(s.observation_time)} (local noon)</p>
    </>
  );
};

const FireDetails: React.FC<{ fire: ActiveFire; stations: FireRiskStation[] }> = ({ fire, stations }) => {
  const near = nearestStationTo(fire, stations);
  return (
    <>
      <Panel className="mb-3 text-sm">
        <div className="mb-2 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full" style={{ backgroundColor: STAGE_COLORS[fire.stage_of_control] }} />
          <span className="font-semibold">{fire.stage_label}</span>
        </div>
        <Row label="Size" value={fmt(fire.hectares, 1, ' ha')} />
        <Row label="Agency" value={fire.agency ?? '—'} />
        <Row label="Started" value={fire.start_date ? String(fire.start_date).slice(0, 10) : '—'} />
      </Panel>
      {near && (
        <Panel className="mb-3 text-sm">
          <div className="mb-1 flex items-center justify-between">
            <span className="text-white/70">Fire danger nearby</span>
            <LevelBadge level={near.risk_level} />
          </div>
          <p className="text-white/75">
            FWI {fmt(near.fire_indices?.fwi, 1)} at {near.station_name}, {near.distance_km.toFixed(0)} km away
          </p>
        </Panel>
      )}
    </>
  );
};

const CustomDetails: React.FC<{ location: FireLocation }> = ({ location }) => (
  <Panel className="mb-3 text-sm">
    <Row label="Location" value={`${location.coordinates.lat.toFixed(3)}, ${location.coordinates.lng.toFixed(3)}`} />
    <Row label="Assumed size" value={fmt((location.area_m2 ?? 0) / 10000, 1, ' ha')} />
  </Panel>
);

const Sidebar: React.FC<SidebarProps> = ({ onShowMission }) => {
  const {
    region, setRegionCode, assessment, fires, hotspots, aqhi, loading, errors, refreshData, selection, setSelection,
    plume, plumeError,
  } = useContext(FireRiskContext);

  const title =
    selection?.kind === 'station' ? selection.station.station_name
      : selection?.kind === 'fire' ? `${selection.fire.name} wildfire`
        : selection?.kind === 'custom' ? 'Placed fire' : null;

  const outOfControl = fires.filter(f => f.stage_of_control === 'OC').length;
  const totalHa = fires.reduce((sum, f) => sum + (f.hectares ?? 0), 0);
  const avgLevel = assessment?.summary.average_level ?? null;

  return (
    <aside className="absolute left-0 top-0 z-20 flex h-full w-[340px] flex-col overflow-y-auto bg-gray-900/85 p-5 text-white backdrop-blur-lg sm:w-[380px]">
      <header className="mb-4">
        <h1 className="text-2xl font-bold">Respira</h1>
        <p className="text-sm text-white/70">Wildfire and smoke conditions across Canada</p>
        <div className="mt-3 flex gap-2">
          <label htmlFor="region" className="sr-only">Province or territory</label>
          <select
            id="region"
            value={region.code}
            onChange={e => setRegionCode(e.target.value)}
            className="flex-1 rounded-md border border-white/20 bg-gray-800 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-orange-400"
          >
            {REGIONS.map(r => <option key={r.code} value={r.code}>{r.name}</option>)}
          </select>
          <button
            onClick={refreshData}
            disabled={loading}
            aria-label="Refresh data"
            className="rounded-md px-3 hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-orange-400 disabled:opacity-50"
          >
            {loading ? <LoadingSpinner size="sm" /> : '↻'}
          </button>
        </div>
      </header>

      {selection ? (
        <section>
          <div className="mb-3 flex items-center">
            <button
              onClick={() => setSelection(null)}
              aria-label="Back to overview"
              className="mr-2 rounded-full p-2 hover:bg-white/15 focus:outline-none focus:ring-2 focus:ring-orange-400"
            >
              ←
            </button>
            <h2 className="truncate text-xl font-bold" title={title ?? ''}>{title}</h2>
          </div>
          {selection.kind === 'station' && <StationDetails s={selection.station} />}
          {selection.kind === 'fire' && <FireDetails fire={selection.fire} stations={assessment?.assessments ?? []} />}
          {selection.kind === 'custom' && <CustomDetails location={selection.location} />}
          <h3 className="mb-1 text-sm font-semibold text-white/90">Smoke projection</h3>
          <SmokeSummary plume={plume} error={plumeError} />
        </section>
      ) : (
        <section className="space-y-4">
          {errors.assessment ? (
            <p className="rounded-lg bg-red-900/60 p-3 text-sm">{errors.assessment}</p>
          ) : !assessment ? (
            <div className="p-8"><LoadingSpinner /></div>
          ) : (
            <>
              <Panel>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-white/70">Typical fire danger</span>
                  <LevelBadge level={avgLevel} />
                </div>
                <p className="mt-2 text-sm text-white/75">
                  {assessment.reporting_fwi} of {assessment.total_stations} stations reporting.{' '}
                  {assessment.high_risk_count} at high or above.
                </p>
              </Panel>
              {assessment.summary.highest_risk && (
                <button
                  onClick={() => setSelection({ kind: 'station', station: assessment.summary.highest_risk! })}
                  className="w-full rounded-lg bg-black/25 p-3 text-left hover:bg-black/40 focus:outline-none focus:ring-2 focus:ring-orange-400"
                >
                  <span className="text-sm text-white/70">Highest danger</span>
                  <div className="font-semibold">{assessment.summary.highest_risk.station_name}</div>
                  <div className="text-sm" style={{ color: riskColor(assessment.summary.highest_risk.risk_level) }}>
                    FWI {fmt(assessment.summary.highest_risk.fire_indices?.fwi, 1)}, {riskInfoForLevel(assessment.summary.highest_risk.risk_level)?.label.toLowerCase()}
                  </div>
                </button>
              )}
            </>
          )}

          <div>
            <h3 className="mb-1 text-sm font-semibold text-white/90">Reported wildfires</h3>
            {errors.fires ? <p className="text-sm text-red-300">{errors.fires}</p> : (
              <Panel className="text-sm">
                <Row label="Active fires" value={fires.length} />
                <Row label="Out of control" value={<span style={{ color: STAGE_COLORS.OC }}>{outOfControl}</span>} />
                <Row label="Area burning" value={`${Math.round(totalHa).toLocaleString('en-CA')} ha`} />
                <Row label="Satellite hotspots (24 h)" value={errors.hotspots ? '—' : hotspots.length} />
                {fires[0] && (
                  <button onClick={() => setSelection({ kind: 'fire', fire: fires[0] })} className="mt-2 text-left text-orange-300 underline-offset-2 hover:underline">
                    Largest: {fires[0].name}, {fmt(fires[0].hectares, 0, ' ha')}
                  </button>
                )}
              </Panel>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-sm font-semibold text-white/90">Air Quality Health Index</h3>
            {errors.aqhi ? <p className="text-sm text-red-300">{errors.aqhi}</p> : aqhi.length === 0 ? (
              <p className="text-sm text-white/60">No communities reporting in this area right now.</p>
            ) : (
              <Panel className="text-sm">
                {aqhi.slice(0, 6).map(o => (
                  <div key={o.location_id ?? o.location_name} className="flex items-center justify-between py-0.5">
                    <span>{o.location_name}</span>
                    <span className="rounded px-2 font-semibold text-white" style={{ backgroundColor: aqhiColor(o.aqhi) }}>
                      {o.aqhi > 10 ? '10+' : o.aqhi.toFixed(0)}
                    </span>
                  </div>
                ))}
                {aqhi[0] && aqhi[0].aqhi >= 4 && <p className="mt-2 text-xs text-white/60">{aqhi[0].location_name}: {aqhi[0].advice}</p>}
              </Panel>
            )}
          </div>
          {assessment && <p className="text-xs text-white/50">Updated {formatTimestamp(assessment.assessment_time)}</p>}
        </section>
      )}

      <div className="flex-grow" />
      <p className="mt-4 text-xs text-white/45">
        Data: Natural Resources Canada (CWFIS), Environment and Climate Change Canada. For evacuation orders and fire bans, check your provincial or territorial wildfire agency.
      </p>
      <button
        onClick={onShowMission}
        className="mt-3 w-full rounded-lg bg-white/10 px-4 py-2.5 font-semibold text-white/85 hover:bg-white/20 focus:outline-none focus:ring-2 focus:ring-orange-400"
      >
        About Respira
      </button>
    </aside>
  );
};

export default Sidebar;
