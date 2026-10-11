import React, { useCallback, useContext, useState } from 'react';
import ChatPanel from './components/ChatPanel';
import ControlPanel from './components/ControlPanel';
import EnhancedMap from './components/EnhancedMap';
import ErrorBoundary from './components/ErrorBoundary';
import FireRiskLegend from './components/FireRiskLegend';
import MissionPopup from './components/MissionPopup';
import Sidebar from './components/Sidebar';
import { FireRiskContext, FireRiskProvider } from './context/FireRiskContext';
import { LayerState } from './types';

const AppContent: React.FC = () => {
  const { fireLocations, clearFireLocations } = useContext(FireRiskContext);
  const [layers, setLayers] = useState<LayerState>({
    heatmap: true, stations: true, fires: true, hotspots: false, aqhi: true, smoke: false, plumes: true,
  });
  const [isPlacingFire, setIsPlacingFire] = useState(false);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [isAboutOpen, setIsAboutOpen] = useState(true);

  const toggleLayer = useCallback((key: keyof LayerState) => setLayers(l => ({ ...l, [key]: !l[key] })), []);
  const onFirePlaced = useCallback(() => setIsPlacingFire(false), []);

  return (
    <div className="relative h-screen w-screen overflow-hidden bg-gray-800">
      <main className="h-full w-full">
        <EnhancedMap layers={layers} isPlacingFire={isPlacingFire} onFirePlaced={onFirePlaced} />
      </main>
      <Sidebar onShowMission={() => setIsAboutOpen(true)} />
      <FireRiskLegend />
      <ControlPanel
        layers={layers}
        toggleLayer={toggleLayer}
        isPlacingFire={isPlacingFire}
        onPlaceFire={() => setIsPlacingFire(p => !p)}
        onClearFires={clearFireLocations}
        fireCount={fireLocations.length}
        onOpenChat={() => setIsChatOpen(true)}
      />
      <ChatPanel isOpen={isChatOpen} onClose={() => setIsChatOpen(false)} />
      <MissionPopup isOpen={isAboutOpen} onClose={() => setIsAboutOpen(false)} />
    </div>
  );
};

const App: React.FC = () => (
  <ErrorBoundary>
    <FireRiskProvider>
      <AppContent />
    </FireRiskProvider>
  </ErrorBoundary>
);

export default App;
