import React, { useState, useEffect } from 'react';
import { getScans, getAdConfig, updateAdConfig, clearHistory } from '../services/storageService';
import { ScanResult, AdConfig } from '../types';
import { Settings, Lock, Database, Trash2, LayoutDashboard, LogOut } from 'lucide-react';

export const Admin: React.FC = () => {
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [password, setPassword] = useState('');
  const [scans, setScans] = useState<ScanResult[]>([]);
  const [adConfig, setAdConfig] = useState<AdConfig | null>(null);

  useEffect(() => {
    if (isAuthenticated) {
      loadData();
    }
  }, [isAuthenticated]);

  const loadData = async () => {
    const s = await getScans();
    const c = await getAdConfig();
    setScans(s);
    setAdConfig(c);
  };

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (password === 'admin123') { // Simple mock auth
      setIsAuthenticated(true);
    } else {
      alert('Access Denied');
    }
  };

  const toggleAdSetting = async (key: keyof AdConfig) => {
    if (!adConfig) return;
    const newConfig = { ...adConfig, [key]: !adConfig[key] };
    setAdConfig(newConfig);
    await updateAdConfig(newConfig);
  };

  const handleClearHistory = async () => {
    if(confirm('Are you sure you want to delete all scan logs? This action cannot be undone.')) {
        await clearHistory();
        loadData();
    }
  }

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 p-4">
        <div className="bg-white p-8 rounded-lg border border-gray-200 shadow-lg w-full max-w-md">
          <div className="flex justify-center mb-6">
            <div className="bg-blue-50 p-3 rounded-full">
               <Lock className="w-6 h-6 text-brand-blue" />
            </div>
          </div>
          <h2 className="text-2xl font-bold text-gray-900 text-center mb-2">Admin Authentication</h2>
          <p className="text-gray-500 text-center mb-8 text-sm">Please enter your credentials to access the control panel.</p>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Enter password"
                className="w-full bg-white border border-gray-300 text-gray-900 px-4 py-3 rounded-md focus:ring-2 focus:ring-brand-blue focus:border-transparent outline-none transition-all"
              />
            </div>
            <button
              type="submit"
              className="w-full bg-brand-blue text-white font-medium py-3 rounded-md hover:bg-blue-700 transition-colors shadow-sm"
            >
              Access Dashboard
            </button>
          </form>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 text-gray-900 pb-12">
      <div className="bg-white border-b border-gray-200 mb-8">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
             <LayoutDashboard className="text-gray-400" />
             <h1 className="text-xl font-bold text-gray-800">Administrator Console</h1>
          </div>
          <button 
            onClick={() => setIsAuthenticated(false)} 
            className="flex items-center gap-2 text-sm text-gray-600 hover:text-red-600 transition-colors"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          
          {/* Ad Control Center */}
          <div className="bg-white border border-gray-200 rounded-lg shadow-sm h-fit overflow-hidden">
            <div className="p-5 border-b border-gray-100 bg-gray-50/50">
               <div className="flex items-center gap-2">
                 <Settings className="w-5 h-5 text-gray-500" />
                 <h2 className="font-semibold text-gray-800">Ads Configuration</h2>
               </div>
            </div>
            
            <div className="p-6">
              {adConfig && (
                <div className="space-y-6">
                  <div className="flex items-center justify-between">
                    <div>
                      <span className="font-medium text-gray-900 block">Global Ads</span>
                      <span className="text-xs text-gray-500">Master switch for all units</span>
                    </div>
                    <button 
                      onClick={() => toggleAdSetting('showAds')}
                      className={`w-11 h-6 rounded-full relative transition-colors ${adConfig.showAds ? 'bg-brand-blue' : 'bg-gray-200'}`}
                    >
                      <span className={`absolute top-1 left-1 w-4 h-4 bg-white rounded-full transition-transform shadow-sm ${adConfig.showAds ? 'translate-x-5' : ''}`} />
                    </button>
                  </div>

                  <div className={`space-y-3 pt-4 border-t border-gray-100 ${!adConfig.showAds ? 'opacity-50 pointer-events-none' : ''}`}>
                     {['headerAd', 'sidebarAd', 'resultAd'].map((setting) => (
                         <div key={setting} className="flex items-center justify-between">
                             <span className="text-sm text-gray-600 capitalize">{setting.replace('Ad', ' Slot')}</span>
                             <input 
                               type="checkbox" 
                               checked={adConfig[setting as keyof AdConfig] as boolean}
                               onChange={() => toggleAdSetting(setting as keyof AdConfig)}
                               className="w-4 h-4 text-brand-blue rounded border-gray-300 focus:ring-brand-blue"
                             />
                         </div>
                     ))}
                  </div>
                </div>
              )}
            </div>
            <div className="bg-blue-50 p-4 border-t border-blue-100">
                <p className="text-xs text-blue-700">
                   Changes to ad slots are reflected immediately across the user application.
                </p>
            </div>
          </div>

          {/* Database Viewer */}
          <div className="lg:col-span-2 bg-white border border-gray-200 rounded-lg shadow-sm overflow-hidden">
             <div className="p-5 border-b border-gray-100 bg-gray-50/50 flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <Database className="w-5 h-5 text-gray-500" />
                    <h2 className="font-semibold text-gray-800">Scan History Database</h2>
                </div>
                <button 
                    onClick={handleClearHistory} 
                    className="text-red-600 hover:text-red-700 hover:bg-red-50 p-2 rounded-md transition-colors"
                    title="Clear Database"
                >
                    <Trash2 className="w-5 h-5" />
                </button>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                    <thead>
                        <tr className="bg-gray-50 text-xs uppercase text-gray-500 font-semibold tracking-wider">
                            <th className="p-4 border-b border-gray-200">Date & Time</th>
                            <th className="p-4 border-b border-gray-200">Verdict</th>
                            <th className="p-4 border-b border-gray-200">Confidence</th>
                            <th className="p-4 border-b border-gray-200 text-right">Preview</th>
                        </tr>
                    </thead>
                    <tbody className="text-sm divide-y divide-gray-100">
                        {scans.length === 0 ? (
                            <tr><td colSpan={4} className="p-8 text-center text-gray-500 italic">No scan records found in database.</td></tr>
                        ) : (
                            scans.map((scan) => (
                                <tr key={scan.id} className="hover:bg-gray-50 transition-colors">
                                    <td className="p-4 text-gray-600 font-mono text-xs">{new Date(scan.timestamp).toLocaleString()}</td>
                                    <td className="p-4">
                                        <span className={`px-2 py-1 rounded text-xs font-medium ${scan.isAi ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'}`}>
                                            {scan.isAi ? 'AI Generated' : 'Authentic'}
                                        </span>
                                    </td>
                                    <td className="p-4 text-gray-700">{scan.confidence}%</td>
                                    <td className="p-4 text-right">
                                        <div className="flex justify-end">
                                            <img src={scan.imageUrl} alt="thumbnail" className="w-12 h-12 object-cover rounded border border-gray-200 shadow-sm" />
                                        </div>
                                    </td>
                                </tr>
                            ))
                        )}
                    </tbody>
                </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};