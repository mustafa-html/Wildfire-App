import React from 'react';
import {
  FiActivity, FiAlertTriangle, FiCloud, FiCrosshair, FiMapPin, FiMessageSquare, FiPlusCircle, FiThermometer,
  FiTrash2, FiWind,
} from 'react-icons/fi';
import { LayerState } from '../types';

interface ControlPanelProps {
  layers: LayerState;
  toggleLayer: (key: keyof LayerState) => void;
  isPlacingFire: boolean;
  onPlaceFire: () => void;
  onClearFires: () => void;
  fireCount: number;
  onOpenChat: () => void;
}

const LAYER_BUTTONS: { key: keyof LayerState; label: string; icon: React.ReactNode }[] = [
  { key: 'heatmap', label: 'Fire danger heatmap', icon: <FiThermometer size={20} /> },
  { key: 'stations', label: 'Weather stations', icon: <FiMapPin size={20} /> },
  { key: 'fires', label: 'Reported wildfires', icon: <FiAlertTriangle size={20} /> },
  { key: 'hotspots', label: 'Satellite hotspots (24 h)', icon: <FiCrosshair size={20} /> },
  { key: 'aqhi', label: 'Air Quality Health Index', icon: <FiActivity size={20} /> },
  { key: 'smoke', label: 'Smoke forecast (ECCC FireWork)', icon: <FiCloud size={20} /> },
  { key: 'plumes', label: 'Smoke projection', icon: <FiWind size={20} /> },
];

const ControlButton: React.FC<{
  label: string;
  icon: React.ReactNode;
  onClick: () => void;
  pressed?: boolean;
}> = ({ label, icon, onClick, pressed }) => (
  <button
    onClick={onClick}
    aria-label={label}
    aria-pressed={pressed}
    className={`group relative flex h-11 w-11 items-center justify-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400
      ${pressed ? 'bg-orange-500 text-white' : 'text-white/75 hover:bg-white/20'}`}
  >
    {icon}
    <span className="pointer-events-none absolute bottom-full mb-2 hidden whitespace-nowrap rounded bg-gray-800 px-2 py-1 text-xs text-white group-hover:block group-focus-visible:block">
      {label}
    </span>
  </button>
);

const ControlPanel: React.FC<ControlPanelProps> = ({
  layers, toggleLayer, isPlacingFire, onPlaceFire, onClearFires, fireCount, onOpenChat,
}) => (
  <div className="absolute bottom-5 left-[calc(50%+190px)] z-20 flex -translate-x-1/2 items-center gap-1 rounded-full bg-gray-900/85 p-1.5 shadow-2xl backdrop-blur-lg max-lg:left-auto max-lg:right-3 max-lg:translate-x-0">
    {LAYER_BUTTONS.map(b => (
      <ControlButton key={b.key} label={b.label} icon={b.icon} pressed={layers[b.key]} onClick={() => toggleLayer(b.key)} />
    ))}
    <div className="mx-1 h-7 w-px bg-white/20" />
    <ControlButton
      label={isPlacingFire ? 'Click the map to place a fire' : 'Place a fire to see its smoke'}
      icon={<FiPlusCircle size={20} />}
      pressed={isPlacingFire}
      onClick={onPlaceFire}
    />
    {fireCount > 0 && (
      <ControlButton label={`Remove placed fires (${fireCount})`} icon={<FiTrash2 size={20} />} onClick={onClearFires} />
    )}
    <ControlButton label="Ask the assistant" icon={<FiMessageSquare size={20} />} onClick={onOpenChat} />
  </div>
);

export default ControlPanel;
