import axios from 'axios';
import {
  ActiveFire, AqhiObservation, FireRiskAssessment, Focus, Hotspot, PlumeData,
} from '../types';
import { API_BASE_URL, PLUME_HOURS, USER_FIRE_AREA_M2 } from '../utils/constants';

const http = axios.create({ baseURL: API_BASE_URL, timeout: 45000 });

const describe = (error: any, what: string): Error => {
  if (error?.response?.data?.detail) return new Error(`${what}: ${error.response.data.detail}`);
  if (error?.request && !error?.response) return new Error(`${what}: the Respira API at ${API_BASE_URL} did not respond.`);
  return new Error(`${what}: ${error?.message ?? 'unknown error'}`);
};

async function get<T>(url: string, params: Record<string, any>, what: string): Promise<T> {
  try {
    return (await http.get<T>(url, { params })).data;
  } catch (e) {
    throw describe(e, what);
  }
}

async function post<T>(url: string, body: Record<string, any>, what: string): Promise<T> {
  try {
    return (await http.post<T>(url, body)).data;
  } catch (e) {
    throw describe(e, what);
  }
}

const apiService = {
  fetchAssessment: (region: string) =>
    get<FireRiskAssessment>('/api/fire-risk/assessment', { region }, 'Fire danger'),

  fetchActiveFires: async (region: string) =>
    (await get<{ fires: ActiveFire[] }>('/api/fires/active', { region }, 'Active fires')).fires,

  fetchHotspots: async (region: string) =>
    (await get<{ hotspots: Hotspot[] }>('/api/fires/hotspots', { region }, 'Hotspots')).hotspots,

  fetchAqhi: async (region: string) =>
    (await get<{ observations: AqhiObservation[] }>('/api/air/aqhi/observations', { region }, 'Air quality')).observations,

  plumeForStation: (stationId: string, region: string) =>
    get<PlumeData>(`/api/stations/${encodeURIComponent(stationId)}/plume`, { region, hours: PLUME_HOURS },
      'Smoke projection'),

  plumeForPoint: (lat: number, lng: number, opts: { hectares?: number | null; area_m2?: number } = {}) =>
    post<PlumeData>('/api/plume', {
      lat,
      lon: lng,
      hours: PLUME_HOURS,
      ...(opts.hectares ? { hectares: opts.hectares } : { area_m2: opts.area_m2 ?? USER_FIRE_AREA_M2 }),
    }, 'Smoke projection'),

  sendChatMessage: (message: string, sessionId: string, focus: Focus | null) =>
    post<{ response: string; sources: string[] }>('/api/llm/chat', {
      message,
      session_id: sessionId,
      location: focus ?? undefined,
    }, 'Assistant'),
};

export default apiService;
