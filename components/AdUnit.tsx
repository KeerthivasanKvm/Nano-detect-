import React from 'react';

interface AdUnitProps {
  location: 'header' | 'sidebar' | 'result';
  enabled: boolean;
}

export const AdUnit: React.FC<AdUnitProps> = ({ location, enabled }) => {
  if (!enabled) return null;

  const sizeClasses = {
    header: 'w-full h-24',
    sidebar: 'w-64 h-full min-h-[400px]',
    result: 'w-full h-32',
  };

  return (
    <div className={`bg-gray-100 border border-gray-200 flex flex-col items-center justify-center relative overflow-hidden my-6 rounded ${sizeClasses[location]}`}>
      <span className="text-[10px] text-gray-400 absolute top-1 right-2 uppercase tracking-wider">Advertisement</span>
      <div className="text-center p-4">
        <h4 className="text-gray-400 font-bold tracking-widest text-sm">GOOGLE ADS</h4>
        <p className="text-gray-400 text-xs mt-1">Placement: {location}</p>
      </div>
    </div>
  );
};