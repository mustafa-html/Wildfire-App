import React from 'react';

interface MissionPopupProps {
  isOpen: boolean;
  onClose: () => void;
}

const MissionPopup: React.FC<MissionPopupProps> = ({ isOpen, onClose }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4" role="dialog" aria-labelledby="about-title">
      <div className="max-w-lg rounded-lg bg-white p-8 shadow-xl">
        <h2 id="about-title" className="mb-4 text-2xl font-bold text-gray-800">About Respira</h2>
        <p className="mb-3 text-gray-700">
          Respira puts Canada's public wildfire and air-quality data on one map: fire danger from the Fire Weather Index
          at hundreds of weather stations, wildfires reported by provincial and territorial agencies, satellite hotspots,
          and the Air Quality Health Index.
        </p>
        <p className="mb-6 text-gray-700">
          Select a station or a fire to see where its smoke could drift. Projections are rough estimates. For evacuation
          orders and fire bans, follow your provincial or territorial wildfire agency and local emergency alerts.
        </p>
        <button
          onClick={onClose}
          className="rounded-lg bg-orange-600 px-6 py-2 font-semibold text-white hover:bg-orange-700 focus:outline-none focus:ring-2 focus:ring-orange-400"
        >
          Open the map
        </button>
      </div>
    </div>
  );
};

export default MissionPopup;
