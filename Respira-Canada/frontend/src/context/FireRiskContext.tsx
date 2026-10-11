import React, { createContext, ReactNode, useCallback, useMemo, useState } from 'react';
import {
  ActiveFire, AqhiObservation, Coordinates, FireLocation, FireRiskAssessment, Focus, Hotspot, PlumeData,
  RegionInfo, Selection,
} from '../types';
import { LayerErrors, useFireRiskData } from '../hooks/useFireRiskData';
import { DEFAULT_REGION, REGIONS } from '../utils/constants';

interface FireRiskContextType {
  region: RegionInfo;
  setRegionCode: (code: string) => void;
  assessment: FireRiskAssessment | null;
  fires: ActiveFire[];
  hotspots: Hotspot[];
  aqhi: AqhiObservation[];
  loading: boolean;
  errors: LayerErrors;
  refreshData: () => void;
  selection: Selection;
  setSelection: (s: Selection) => void;
  plume: PlumeData | null;
  plumeError: string | null;
  setPlume: (p: PlumeData | null, error?: string | null) => void;
  fireLocations: FireLocation[];
  addFireLocation: (location: FireLocation) => void;
  clearFireLocations: () => void;
  setMapCenter: (c: Coordinates) => void;
  focus: Focus | null;
}

export const FireRiskContext = createContext<FireRiskContextType>(null as unknown as FireRiskContextType);

const findRegion = (code: string): RegionInfo =>
  REGIONS.find(r => r.code === code) ?? REGIONS.find(r => r.code === 'AB')!;

export const FireRiskProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [regionCode, setRegionCodeState] = useState(findRegion(DEFAULT_REGION).code);
  const region = findRegion(regionCode);
  const data = useFireRiskData(regionCode);
  const [selection, setSelection] = useState<Selection>(null);
  const [plume, setPlumeState] = useState<PlumeData | null>(null);
  const [plumeError, setPlumeError] = useState<string | null>(null);
  const [fireLocations, setFireLocations] = useState<FireLocation[]>([]);
  const [mapCenter, setMapCenter] = useState<Coordinates>(region.center);

  const setRegionCode = useCallback((code: string) => {
    setRegionCodeState(code);
    setSelection(null);
    setPlumeState(null);
  }, []);

  const setPlume = useCallback((p: PlumeData | null, error: string | null = null) => {
    setPlumeState(p);
    setPlumeError(error);
  }, []);

  const addFireLocation = useCallback((l: FireLocation) => setFireLocations(prev => [...prev, l]), []);
  const clearFireLocations = useCallback(() => {
    setFireLocations([]);
    setSelection(prev => (prev?.kind === 'custom' ? null : prev));
  }, []);

  const focus = useMemo<Focus | null>(() => {
    if (selection?.kind === 'station') {
      const s = selection.station;
      return { latitude: s.latitude, longitude: s.longitude, name: `${s.station_name} weather station` };
    }
    if (selection?.kind === 'fire') {
      const f = selection.fire;
      return { latitude: f.latitude, longitude: f.longitude, name: `${f.name} wildfire` };
    }
    if (selection?.kind === 'custom') {
      const c = selection.location.coordinates;
      return { latitude: c.lat, longitude: c.lng, name: 'The fire placed on the map' };
    }
    return { latitude: mapCenter.lat, longitude: mapCenter.lng, name: `Map centre (${region.name})` };
  }, [selection, mapCenter, region.name]);

  return (
    <FireRiskContext.Provider
      value={{
        region, setRegionCode, ...data, selection, setSelection, plume, plumeError, setPlume,
        fireLocations, addFireLocation, clearFireLocations, setMapCenter, focus,
      }}
    >
      {children}
    </FireRiskContext.Provider>
  );
};
