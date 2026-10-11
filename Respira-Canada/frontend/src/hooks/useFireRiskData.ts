import { useCallback, useEffect, useRef, useState } from 'react';
import { ActiveFire, AqhiObservation, FireRiskAssessment, Hotspot } from '../types';
import apiService from '../services/apiService';
import { UPDATE_INTERVAL } from '../utils/constants';

export interface LayerErrors {
  assessment?: string;
  fires?: string;
  hotspots?: string;
  aqhi?: string;
}

export const useFireRiskData = (region: string) => {
  const [assessment, setAssessment] = useState<FireRiskAssessment | null>(null);
  const [fires, setFires] = useState<ActiveFire[]>([]);
  const [hotspots, setHotspots] = useState<Hotspot[]>([]);
  const [aqhi, setAqhi] = useState<AqhiObservation[]>([]);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState<LayerErrors>({});
  const requestId = useRef(0);

  const fetchData = useCallback(async () => {
    const id = ++requestId.current;
    setLoading(true);
    const [a, f, h, q] = await Promise.allSettled([
      apiService.fetchAssessment(region),
      apiService.fetchActiveFires(region),
      apiService.fetchHotspots(region),
      apiService.fetchAqhi(region),
    ]);
    if (id !== requestId.current) return; // a newer region was requested meanwhile
    const errs: LayerErrors = {};
    if (a.status === 'fulfilled') setAssessment(a.value); else { setAssessment(null); errs.assessment = a.reason.message; }
    if (f.status === 'fulfilled') setFires(f.value); else { setFires([]); errs.fires = f.reason.message; }
    if (h.status === 'fulfilled') setHotspots(h.value); else { setHotspots([]); errs.hotspots = h.reason.message; }
    if (q.status === 'fulfilled') setAqhi(q.value); else { setAqhi([]); errs.aqhi = q.reason.message; }
    setErrors(errs);
    setLoading(false);
  }, [region]);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, UPDATE_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  return { assessment, fires, hotspots, aqhi, loading, errors, refreshData: fetchData };
};
