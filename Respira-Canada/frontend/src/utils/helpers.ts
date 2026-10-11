import { NO_FWI_COLOR, RISK_LEVELS } from './constants';
import { ActiveFire, FireRiskStation, RiskLevel, RiskLevelInfo } from '../types';

export const riskInfoForLevel = (level: RiskLevel | null | undefined): RiskLevelInfo | null =>
  level ? RISK_LEVELS[level] ?? null : null;

export const riskColor = (level: RiskLevel | null | undefined): string =>
  riskInfoForLevel(level)?.color ?? NO_FWI_COLOR;

export const fmt = (value: number | null | undefined, digits = 0, unit = ''): string =>
  value === null || value === undefined || Number.isNaN(value) ? '—' : `${value.toFixed(digits)}${unit}`;

export const formatTimestamp = (timestamp?: string | null): string => {
  if (!timestamp) return '—';
  const date = new Date(timestamp.includes('T') ? timestamp : timestamp.replace(' ', 'T'));
  if (Number.isNaN(date.getTime())) return timestamp;
  return date.toLocaleString('en-CA', { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' });
};

export const windCardinal = (degrees: number | null | undefined): string => {
  if (degrees === null || degrees === undefined) return '';
  if (degrees === 271) return 'variable';
  const dirs = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'];
  return dirs[Math.round(degrees / 45) % 8];
};

export const aqhiColor = (aqhi: number): string => {
  if (aqhi <= 3) return '#0284c7';
  if (aqhi <= 6) return '#ca8a04';
  if (aqhi <= 10) return '#dc2626';
  return '#7f1d1d';
};

export const fireMarkerScale = (hectares: number | null): number =>
  Math.min(18, 5 + Math.log10(Math.max(hectares ?? 0.1, 0.1) + 1) * 3);

export const haversineKm = (lat1: number, lon1: number, lat2: number, lon2: number): number => {
  const toRad = (d: number) => (d * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a = Math.sin(dLat / 2) ** 2 + Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
};

export const nearestStationTo = (
  fire: Pick<ActiveFire, 'latitude' | 'longitude'>,
  stations: FireRiskStation[],
): (FireRiskStation & { distance_km: number }) | null => {
  let best: (FireRiskStation & { distance_km: number }) | null = null;
  for (const s of stations) {
    if (s.risk_score === null) continue;
    const d = haversineKm(fire.latitude, fire.longitude, s.latitude, s.longitude);
    if (!best || d < best.distance_km) best = { ...s, distance_km: d };
  }
  return best;
};
