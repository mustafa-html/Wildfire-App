import React, { useContext, useEffect, useRef, useState } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { FireRiskContext } from '../context/FireRiskContext';
import { useGoogleMaps } from '../hooks/useGoogleMaps';
import apiService from '../services/apiService';
import { FireLocation, LayerState } from '../types';
import { HEATMAP_GRADIENT, SMOKE_WMS, STAGE_COLORS, USER_FIRE_AREA_M2 } from '../utils/constants';
import { aqhiColor, fireMarkerScale, fmt, riskColor } from '../utils/helpers';

interface EnhancedMapProps {
  layers: LayerState;
  isPlacingFire: boolean;
  onFirePlaced: () => void;
}

const HALF_WORLD = 20037508.342789244;

const EnhancedMap: React.FC<EnhancedMapProps> = ({ layers, isPlacingFire, onFirePlaced }) => {
  const {
    region, assessment, fires, hotspots, aqhi, selection, setSelection, plume, setPlume,
    fireLocations, addFireLocation, setMapCenter,
  } = useContext(FireRiskContext);
  const { isLoaded, loadError } = useGoogleMaps();

  const mapRef = useRef<HTMLDivElement>(null);
  const [map, setMap] = useState<any>(null);
  const placingRef = useRef(isPlacingFire);
  const plumeRequest = useRef(0);
  const plumePolygon = useRef<any>(null);
  const animationFrame = useRef<number | null>(null);

  placingRef.current = isPlacingFire;

  // --- map ---------------------------------------------------------------
  useEffect(() => {
    if (!isLoaded || !mapRef.current || map) return;
    const g = window.google;
    const m = new g.maps.Map(mapRef.current, {
      center: region.center,
      zoom: region.zoom,
      mapTypeControl: true,
      streetViewControl: false,
      fullscreenControl: false,
      mapTypeId: 'terrain',
    });
    m.addListener('click', (event: any) => {
      if (!placingRef.current) return;
      const location: FireLocation = {
        id: uuidv4(),
        coordinates: { lat: event.latLng.lat(), lng: event.latLng.lng() },
        timestamp: new Date().toISOString(),
        area_m2: USER_FIRE_AREA_M2,
      };
      addFireLocation(location);
      setSelection({ kind: 'custom', location });
      onFirePlaced();
    });
    m.addListener('idle', () => {
      const c = m.getCenter();
      if (c) setMapCenter({ lat: c.lat(), lng: c.lng() });
    });
    setMap(m);
  }, [isLoaded, map, region, addFireLocation, setSelection, setMapCenter, onFirePlaced]);

  useEffect(() => {
    if (!map) return;
    map.setCenter(region.center);
    map.setZoom(region.zoom);
  }, [map, region]);

  useEffect(() => {
    if (map) map.setOptions({ draggableCursor: isPlacingFire ? 'crosshair' : null });
  }, [map, isPlacingFire]);

  // --- stations + heatmap ------------------------------------------------
  useEffect(() => {
    if (!map || !assessment) return;
    const g = window.google;
    const objects: any[] = [];
    const scored = assessment.assessments.filter(s => s.risk_score !== null);

    if (layers.heatmap && g.maps.visualization && scored.length) {
      const data = scored.flatMap(s => {
        const weight = Math.max(0.1, Math.min(1, (s.risk_score as number) / 100));
        const pts = [{ location: new g.maps.LatLng(s.latitude, s.longitude), weight }];
        for (let i = 0; i < 12; i++) {
          const a = (2 * Math.PI * i) / 12;
          pts.push({ location: new g.maps.LatLng(s.latitude + 0.25 * Math.cos(a), s.longitude + 0.35 * Math.sin(a)), weight: weight * 0.6 });
        }
        return pts;
      });
      objects.push(new g.maps.visualization.HeatmapLayer({
        data, map, radius: 60, opacity: 0.55, gradient: HEATMAP_GRADIENT, maxIntensity: 2, dissipating: true,
      }));
    }

    if (layers.stations) {
      assessment.assessments.forEach(s => {
        const marker = new g.maps.Marker({
          position: { lat: s.latitude, lng: s.longitude },
          map,
          title: `${s.station_name} — ${s.risk_level ? `FWI ${fmt(s.fire_indices?.fwi, 1)}` : 'no FWI reported'}`,
          icon: {
            path: g.maps.SymbolPath.CIRCLE, scale: 6, fillColor: riskColor(s.risk_level), fillOpacity: 0.95,
            strokeColor: '#ffffff', strokeWeight: 1.5,
          },
          zIndex: 10,
        });
        marker.addListener('click', () => setSelection({ kind: 'station', station: s }));
        objects.push(marker);
      });
    }
    return () => objects.forEach(o => o.setMap(null));
  }, [map, assessment, layers.heatmap, layers.stations, setSelection]);

  // --- active fires ------------------------------------------------------
  useEffect(() => {
    if (!map || !layers.fires) return;
    const g = window.google;
    const markers = fires.map(f => {
      const m = new g.maps.Marker({
        position: { lat: f.latitude, lng: f.longitude },
        map,
        title: `${f.name}: ${fmt(f.hectares, 1, ' ha')}, ${f.stage_label.toLowerCase()}`,
        icon: {
          path: g.maps.SymbolPath.CIRCLE, scale: fireMarkerScale(f.hectares), fillColor: STAGE_COLORS[f.stage_of_control],
          fillOpacity: 0.85, strokeColor: '#1f2937', strokeWeight: 1.5,
        },
        zIndex: 30,
      });
      m.addListener('click', () => setSelection({ kind: 'fire', fire: f }));
      return m;
    });
    return () => markers.forEach(m => m.setMap(null));
  }, [map, fires, layers.fires, setSelection]);

  // --- satellite hotspots ------------------------------------------------
  useEffect(() => {
    if (!map || !layers.hotspots) return;
    const g = window.google;
    const markers = hotspots.map(h => new g.maps.Marker({
      position: { lat: h.latitude, lng: h.longitude },
      map,
      clickable: false,
      title: `Hotspot${h.frp_mw ? `, ${h.frp_mw.toFixed(0)} MW` : ''}`,
      icon: { path: g.maps.SymbolPath.CIRCLE, scale: 2.5, fillColor: '#b91c1c', fillOpacity: 0.9, strokeWeight: 0 },
      zIndex: 20,
    }));
    return () => markers.forEach(m => m.setMap(null));
  }, [map, hotspots, layers.hotspots]);

  // --- AQHI --------------------------------------------------------------
  useEffect(() => {
    if (!map || !layers.aqhi) return;
    const g = window.google;
    const markers = aqhi.map(o => new g.maps.Marker({
      position: { lat: o.latitude, lng: o.longitude },
      map,
      title: `${o.location_name}: AQHI ${o.aqhi} (${o.category.toLowerCase()} risk)`,
      label: { text: o.aqhi > 10 ? '10+' : String(Math.round(o.aqhi)), color: '#ffffff', fontSize: '11px', fontWeight: '600' },
      icon: { path: g.maps.SymbolPath.CIRCLE, scale: 11, fillColor: aqhiColor(o.aqhi), fillOpacity: 0.95, strokeColor: '#ffffff', strokeWeight: 1.5 },
      zIndex: 40,
    }));
    return () => markers.forEach(m => m.setMap(null));
  }, [map, aqhi, layers.aqhi]);

  // --- fires placed by the user -----------------------------------------
  useEffect(() => {
    if (!map) return;
    const g = window.google;
    const markers = fireLocations.map(l => {
      const m = new g.maps.Marker({
        position: l.coordinates, map, title: 'Placed fire',
        icon: { path: g.maps.SymbolPath.BACKWARD_CLOSED_ARROW, scale: 5, fillColor: '#f97316', fillOpacity: 1, strokeColor: '#7c2d12', strokeWeight: 1.5 },
        zIndex: 50,
      });
      m.addListener('click', () => setSelection({ kind: 'custom', location: l }));
      return m;
    });
    return () => markers.forEach(m => m.setMap(null));
  }, [map, fireLocations, setSelection]);

  // --- ECCC FireWork smoke forecast overlay (WMS tiles) -------------------
  useEffect(() => {
    if (!map || !layers.smoke) return;
    const g = window.google;
    const smoke = new g.maps.ImageMapType({
      name: 'FireWork smoke forecast',
      tileSize: new g.maps.Size(256, 256),
      opacity: 0.6,
      getTileUrl: (coord: any, zoom: number) => {
        const n = 2 ** zoom;
        const size = (2 * HALF_WORLD) / n;
        const x = ((coord.x % n) + n) % n;
        const minx = -HALF_WORLD + x * size;
        const maxy = HALF_WORLD - coord.y * size;
        return `${SMOKE_WMS.url}?SERVICE=WMS&VERSION=1.3.0&REQUEST=GetMap&LAYERS=${encodeURIComponent(SMOKE_WMS.layer)}`
          + `&STYLES=&CRS=EPSG:3857&BBOX=${minx},${maxy - size},${minx + size},${maxy}`
          + '&WIDTH=256&HEIGHT=256&FORMAT=image/png&TRANSPARENT=TRUE';
      },
    });
    map.overlayMapTypes.push(smoke);
    return () => {
      const arr = map.overlayMapTypes.getArray();
      const i = arr.indexOf(smoke);
      if (i >= 0) map.overlayMapTypes.removeAt(i);
    };
  }, [map, layers.smoke]);

  // --- fetch a smoke projection whenever the selection changes ------------
  useEffect(() => {
    const id = ++plumeRequest.current;
    if (!selection) {
      setPlume(null);
      return;
    }
    const request =
      selection.kind === 'station'
        ? apiService.plumeForStation(selection.station.station_id, region.code)
        : selection.kind === 'fire'
          ? apiService.plumeForPoint(selection.fire.latitude, selection.fire.longitude, { hectares: selection.fire.hectares })
          : apiService.plumeForPoint(selection.location.coordinates.lat, selection.location.coordinates.lng,
              { area_m2: selection.location.area_m2 });
    request
      .then(data => { if (id === plumeRequest.current) setPlume(data); })
      .catch((e: Error) => { if (id === plumeRequest.current) setPlume(null, e.message); });
  }, [selection, region.code, setPlume]);

  // --- animate the plume outward over 8 s ---------------------------------
  useEffect(() => {
    const stop = () => {
      if (animationFrame.current) cancelAnimationFrame(animationFrame.current);
      animationFrame.current = null;
      if (plumePolygon.current) plumePolygon.current.setMap(null);
      plumePolygon.current = null;
    };
    if (!map || !plume || !plume.frames.length || !layers.plumes) {
      stop();
      return;
    }
    const g = window.google;
    const frames = plume.frames;
    const poly = new g.maps.Polygon({
      map, strokeColor: '#78716c', strokeOpacity: 0.9, strokeWeight: 1.5, fillColor: '#a8a29e', fillOpacity: 0.45, clickable: false, zIndex: 5,
    });
    plumePolygon.current = poly;
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
    const duration = reduce ? 0 : 8000;
    const maxHour = frames[frames.length - 1].hours;
    let start: number | null = null;

    const tick = (t: number) => {
      if (start === null) start = t;
      const progress = duration === 0 ? 1 : Math.min((t - start) / duration, 1);
      const target = progress * maxHour;
      let a = frames[0];
      let b = frames[0];
      for (let i = 0; i < frames.length - 1; i++) {
        if (frames[i].hours <= target && frames[i + 1].hours >= target) { a = frames[i]; b = frames[i + 1]; break; }
      }
      if (progress === 1) a = b = frames[frames.length - 1];
      const ca = a.geojson.coordinates[0];
      const cb = b.geojson.coordinates[0];
      const span = b.hours - a.hours;
      const k = span === 0 ? 1 : (target - a.hours) / span;
      const len = Math.min(ca.length, cb.length);
      const path = [];
      for (let i = 0; i < len; i++) {
        path.push({ lat: ca[i][1] + (cb[i][1] - ca[i][1]) * k, lng: ca[i][0] + (cb[i][0] - ca[i][0]) * k });
      }
      poly.setPaths(path);
      if (progress < 1) animationFrame.current = requestAnimationFrame(tick);
    };
    animationFrame.current = requestAnimationFrame(tick);
    return stop;
  }, [map, plume, layers.plumes]);

  if (loadError) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-800 p-8 text-center text-white">
        <p className="max-w-md">Map unavailable. {loadError}</p>
      </div>
    );
  }
  if (!isLoaded) {
    return (
      <div className="flex h-full items-center justify-center bg-gray-800">
        <div className="h-12 w-12 animate-spin rounded-full border-b-2 border-white" aria-label="Loading map" />
      </div>
    );
  }
  return <div ref={mapRef} className="h-full w-full" />;
};

export default EnhancedMap;
