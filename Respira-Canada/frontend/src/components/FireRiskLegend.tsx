import React, { useState } from 'react';
import { NO_FWI_COLOR, RISK_LEVELS, STAGE_COLORS } from '../utils/constants';

const Dot: React.FC<{ color: string }> = ({ color }) => (
  <span className="mr-2 inline-block h-3 w-3 rounded-full" style={{ backgroundColor: color }} />
);

const FireRiskLegend: React.FC = () => {
  const [open, setOpen] = useState(true);
  return (
    <div className="absolute right-3 top-14 z-10 w-56 rounded-xl bg-white/95 p-4 text-sm text-gray-800 shadow-xl backdrop-blur">
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        className="flex w-full items-center justify-between font-semibold focus:outline-none focus-visible:ring-2 focus-visible:ring-orange-400"
      >
        Fire danger (FWI)
        <span aria-hidden>{open ? '−' : '+'}</span>
      </button>
      {open && (
        <>
          <ul className="mt-2 space-y-1">
            {Object.values(RISK_LEVELS).map(l => (
              <li key={l.key} className="flex items-center justify-between">
                <span className="flex items-center"><Dot color={l.color} />{l.label}</span>
                <span className="text-gray-500">{l.fwiRange}</span>
              </li>
            ))}
            <li className="flex items-center"><Dot color={NO_FWI_COLOR} />Not reporting</li>
          </ul>
          <p className="mt-3 font-semibold">Wildfires</p>
          <ul className="mt-1 space-y-1">
            <li className="flex items-center"><Dot color={STAGE_COLORS.OC} />Out of control</li>
            <li className="flex items-center"><Dot color={STAGE_COLORS.BH} />Being held</li>
            <li className="flex items-center"><Dot color={STAGE_COLORS.UC} />Under control</li>
          </ul>
          <p className="mt-3 text-xs text-gray-500">
            Classes follow the CWFIS national FWI map. Provincial danger ratings may differ.
          </p>
        </>
      )}
    </div>
  );
};

export default FireRiskLegend;
