import { RegionInfo, RiskLevel, RiskLevelInfo, StageOfControl } from '../types';

export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
export const GOOGLE_MAPS_API_KEY = process.env.REACT_APP_GOOGLE_MAPS_API_KEY || '';
export const DEFAULT_REGION = (process.env.REACT_APP_DEFAULT_REGION || 'AB').toUpperCase();

// ECCC FireWork smoke forecast (wildfire contribution to PM2.5), served by MSC GeoMet WMS.
export const SMOKE_WMS = {
  url: process.env.REACT_APP_SMOKE_WMS_URL || 'https://geo.weather.gc.ca/geomet',
  layer: process.env.REACT_APP_SMOKE_WMS_LAYER || 'RAQDPS-FW.EATM_PM2.5-DIFF',
};

// Mirrors backend/app/config.py REGIONS.
export const REGIONS: RegionInfo[] = [
  { code: 'CA', name: 'All of Canada', center: { lat: 56.0, lng: -96.0 }, zoom: 4 },
  { code: 'BC', name: 'British Columbia', center: { lat: 54.0, lng: -125.0 }, zoom: 5 },
  { code: 'AB', name: 'Alberta', center: { lat: 54.5, lng: -115.0 }, zoom: 5 },
  { code: 'SK', name: 'Saskatchewan', center: { lat: 54.5, lng: -105.7 }, zoom: 5 },
  { code: 'MB', name: 'Manitoba', center: { lat: 54.5, lng: -97.5 }, zoom: 5 },
  { code: 'ON', name: 'Ontario', center: { lat: 49.5, lng: -85.0 }, zoom: 5 },
  { code: 'QC', name: 'Quebec', center: { lat: 51.5, lng: -71.5 }, zoom: 5 },
  { code: 'NB', name: 'New Brunswick', center: { lat: 46.5, lng: -66.4 }, zoom: 7 },
  { code: 'NS', name: 'Nova Scotia', center: { lat: 45.1, lng: -63.0 }, zoom: 7 },
  { code: 'PE', name: 'Prince Edward Island', center: { lat: 46.4, lng: -63.2 }, zoom: 8 },
  { code: 'NL', name: 'Newfoundland and Labrador', center: { lat: 53.0, lng: -60.0 }, zoom: 5 },
  { code: 'YT', name: 'Yukon', center: { lat: 63.5, lng: -135.5 }, zoom: 5 },
  { code: 'NT', name: 'Northwest Territories', center: { lat: 64.0, lng: -119.0 }, zoom: 4 },
  { code: 'NU', name: 'Nunavut', center: { lat: 64.0, lng: -90.0 }, zoom: 4 },
];

// Score bands match the backend: each CWFIS FWI danger class is one 20-point band.
export const RISK_LEVELS: Record<RiskLevel, RiskLevelInfo> = {
  LOW: { key: 'LOW', label: 'Low', color: '#2563eb', range: [0, 20], fwiRange: '0–5' },
  MODERATE: { key: 'MODERATE', label: 'Moderate', color: '#16a34a', range: [20, 40], fwiRange: '6–15' },
  HIGH: { key: 'HIGH', label: 'High', color: '#eab308', range: [40, 60], fwiRange: '16–22' },
  'VERY HIGH': { key: 'VERY HIGH', label: 'Very high', color: '#f97316', range: [60, 80], fwiRange: '23–29' },
  EXTREME: { key: 'EXTREME', label: 'Extreme', color: '#dc2626', range: [80, 100], fwiRange: '30+' },
};

export const NO_FWI_COLOR = '#9ca3af';

export const STAGE_COLORS: Record<StageOfControl, string> = {
  OC: '#dc2626',
  BH: '#f97316',
  UC: '#eab308',
  EX: '#6b7280',
  UNK: '#6b7280',
};

export const HEATMAP_GRADIENT = [
  'rgba(37, 99, 235, 0)',
  'rgba(37, 99, 235, 0.55)',
  'rgba(22, 163, 74, 0.65)',
  'rgba(234, 179, 8, 0.8)',
  'rgba(249, 115, 22, 0.9)',
  'rgba(220, 38, 38, 1)',
];

export const PLUME_HOURS = [0.5, 1, 2, 3, 4, 5, 6];
export const USER_FIRE_AREA_M2 = 10000;
// CWFIS station data changes once a day and AQHI hourly; 10 minutes is plenty.
export const UPDATE_INTERVAL = 10 * 60 * 1000;
