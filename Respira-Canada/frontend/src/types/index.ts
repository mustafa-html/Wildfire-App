export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'VERY HIGH' | 'EXTREME';

export interface Coordinates {
  lat: number;
  lng: number;
}

export interface RegionInfo {
  code: string;
  name: string;
  center: Coordinates;
  zoom: number;
}

export interface WeatherConditions {
  temperature?: number | null; // °C
  relative_humidity?: number | null; // %
  wind_speed?: number | null; // km/h
  wind_direction?: number | null; // degrees, direction the wind blows from
  wind_gust?: number | null; // km/h
  precip_24h?: number | null; // mm
}

export interface FireIndices {
  ffmc?: number | null;
  dmc?: number | null;
  dc?: number | null;
  isi?: number | null;
  bui?: number | null;
  fwi?: number | null;
  dsr?: number | null;
  calc_status?: number | null;
}

export interface FireRiskStation {
  station_id: string;
  station_name: string;
  latitude: number;
  longitude: number;
  observation_time?: string | null;
  risk_score: number | null;
  risk_level: RiskLevel | null;
  interpretation?: string;
  weather_conditions?: WeatherConditions;
  fire_indices?: FireIndices;
}

export interface FireRiskAssessment {
  assessment_time: string;
  total_stations: number;
  reporting_fwi: number;
  high_risk_count: number;
  summary: {
    highest_risk: FireRiskStation | null;
    average_risk: number;
    average_level: RiskLevel | null;
  };
  assessments: FireRiskStation[];
}

export type StageOfControl = 'OC' | 'BH' | 'UC' | 'EX' | 'UNK';

export interface ActiveFire {
  fire_id: string;
  name: string;
  agency: string | null;
  latitude: number;
  longitude: number;
  hectares: number | null;
  stage_of_control: StageOfControl;
  stage_label: string;
  start_date?: string | null;
}

export interface Hotspot {
  latitude: number;
  longitude: number;
  detected_at?: string | null;
  frp_mw?: number | null;
  sensor?: string | null;
}

export interface AqhiObservation {
  location_id: string | null;
  location_name: string;
  latitude: number;
  longitude: number;
  aqhi: number;
  category: string;
  advice: string;
  observed_at?: string | null;
}

export interface FireLocation {
  id: string;
  coordinates: Coordinates;
  timestamp: string;
  area_m2?: number;
}

export interface PlumeFrame {
  hours: number;
  geojson: { type: string; coordinates: number[][][] };
  meta: Record<string, any>;
}

export interface PlumeData {
  frames: PlumeFrame[];
  source: string;
  inputs?: Record<string, any>;
}

export type Selection =
  | { kind: 'station'; station: FireRiskStation }
  | { kind: 'fire'; fire: ActiveFire }
  | { kind: 'custom'; location: FireLocation }
  | null;

export interface Focus {
  latitude: number;
  longitude: number;
  name: string;
}

export interface LayerState {
  heatmap: boolean;
  stations: boolean;
  fires: boolean;
  hotspots: boolean;
  aqhi: boolean;
  smoke: boolean;
  plumes: boolean;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
  sources?: string[];
}

export interface RiskLevelInfo {
  key: RiskLevel;
  label: string;
  color: string;
  range: [number, number];
  fwiRange: string;
}
