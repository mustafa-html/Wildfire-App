import { useEffect, useState } from 'react';
import { GOOGLE_MAPS_API_KEY } from '../utils/constants';

declare global {
  interface Window {
    google: any;
    initGoogleMaps: () => void;
  }
}

export const useGoogleMaps = () => {
  const [isLoaded, setIsLoaded] = useState<boolean>(!!window.google?.maps?.visualization);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    if (window.google?.maps?.visualization) {
      setIsLoaded(true);
      return;
    }
    if (!GOOGLE_MAPS_API_KEY) {
      setLoadError('Add REACT_APP_GOOGLE_MAPS_API_KEY to frontend/.env and restart the dev server.');
      return;
    }
    window.initGoogleMaps = () => {
      if (window.google?.maps?.visualization) setIsLoaded(true);
      else setLoadError('The Google Maps visualization library did not load.');
    };
    const script = document.createElement('script');
    script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&libraries=visualization&callback=initGoogleMaps`;
    script.async = true;
    script.defer = true;
    script.onerror = () => setLoadError('Google Maps failed to load. Check the API key and network.');
    document.head.appendChild(script);
    return () => {
      if (script.parentNode) script.parentNode.removeChild(script);
    };
  }, []);

  return { isLoaded, loadError };
};
