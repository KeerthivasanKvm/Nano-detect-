import React, { useState, useRef, useEffect } from 'react';
import { Upload, AlertTriangle, CheckCircle, FileSearch, ArrowRight, Loader2, Image as ImageIcon, Sparkles } from 'lucide-react';
import { analyzeImage } from '../services/geminiService';
import { saveScan, getAdConfig } from '../services/storageService';
import { ScanResult, AnalysisStatus, AdConfig } from '../types';
import { AdUnit } from '../components/AdUnit';

export const Scanner: React.FC = () => {
  const [image, setImage] = useState<string | null>(null);
  const [status, setStatus] = useState<AnalysisStatus>(AnalysisStatus.IDLE);
  const [result, setResult] = useState<ScanResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [adConfig, setAdConfig] = useState<AdConfig | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getAdConfig().then(setAdConfig);
  }, []);

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      if (file.size > 5 * 1024 * 1024) {
        setError("File size exceeds 5MB limit.");
        return;
      }
      const reader = new FileReader();
      reader.onloadend = () => {
        setImage(reader.result as string);
        setResult(null);
        setError(null);
        setStatus(AnalysisStatus.IDLE);
      };
      reader.readAsDataURL(file);
    }
  };

  const handleScan = async () => {
    if (!image) return;
    setStatus(AnalysisStatus.SCANNING);
    setError(null);

    const minDelay = new Promise(resolve => setTimeout(resolve, 2000)); // Little longer for the effect
    
    try {
      const mimeType = image.split(';')[0].split(':')[1];
      const base64Data = image.split(',')[1];

      const [analysis, _] = await Promise.all([
          analyzeImage(base64Data, mimeType),
          minDelay
      ]);

      const newScan: ScanResult = {
        id: crypto.randomUUID(),
        timestamp: Date.now(),
        imageUrl: image,
        ...analysis
      };

      setResult(newScan);
      await saveScan(newScan);
      setStatus(AnalysisStatus.COMPLETE);
    } catch (err: any) {
      setError(err.message || "Unknown error occurred");
      setStatus(AnalysisStatus.ERROR);
    }
  };

  return (
    <div className="min-h-screen pb-20 animate-fade-in bg-gray-50/50">
      {adConfig?.showAds && <div className="animate-fade-in-up"><AdUnit location="header" enabled={adConfig.headerAd} /></div>}

      <main className="max-w-6xl mx-auto px-4 mt-12">
        <div className="text-center mb-12 animate-fade-in-up">
          <h1 className="text-3xl md:text-5xl font-extrabold text-gray-900 mb-4">
            Analysis <span className="text-transparent bg-clip-text bg-gradient-brand">Lab</span>
          </h1>
          <p className="text-gray-500 max-w-2xl mx-auto text-lg">
            Upload any image to run our deep-learning forensic model.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Main Interface */}
          <div className="lg:col-span-2 space-y-6">
            
            {/* Upload Area */}
            <div className="bg-white rounded-3xl shadow-xl shadow-indigo-100/50 border border-white p-1 transition-all duration-300 hover:shadow-2xl animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
              
              <div 
                className={`relative rounded-[20px] p-8 transition-all duration-300 overflow-hidden min-h-[400px] flex flex-col justify-center ${
                    image ? 'bg-gray-900' : 'bg-gradient-to-br from-indigo-50/50 to-purple-50/50 border-2 border-dashed border-indigo-200 hover:border-indigo-400'
                }`}
              >
                <input
                  type="file"
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  accept="image/*"
                  className="hidden"
                />
                
                {!image ? (
                  <div 
                    onClick={() => fileInputRef.current?.click()}
                    className="flex flex-col items-center justify-center cursor-pointer group"
                  >
                    <div className="bg-white p-6 rounded-3xl shadow-lg mb-6 group-hover:scale-110 transition-transform duration-300 group-hover:shadow-xl relative overflow-hidden">
                       <div className="absolute inset-0 bg-gradient-brand opacity-0 group-hover:opacity-10 transition-opacity"></div>
                       <Upload className="w-10 h-10 text-indigo-600" />
                    </div>
                    <p className="font-bold text-gray-800 text-lg group-hover:text-indigo-600 transition-colors">Click to Upload Evidence</p>
                    <p className="text-sm text-gray-500 mt-2">JPG, PNG, WEBP supported</p>
                  </div>
                ) : (
                  <div className="relative group w-full h-full flex items-center justify-center">
                    <img src={image} alt="Preview" className="w-full h-full max-h-[500px] object-contain rounded-lg shadow-2xl" />
                    
                    {/* Scanning Overlay Animation */}
                    {status === AnalysisStatus.SCANNING && (
                        <div className="absolute inset-0 z-10 overflow-hidden rounded-lg pointer-events-none">
                            <div className="absolute top-0 left-0 w-full h-1 bg-gradient-brand shadow-[0_0_30px_rgba(168,85,247,0.8)] animate-scan-line"></div>
                            <div className="absolute inset-0 bg-indigo-500/10 mix-blend-overlay"></div>
                        </div>
                    )}

                    {status !== AnalysisStatus.SCANNING && (
                       <button 
                       onClick={() => { setImage(null); setResult(null); }}
                       className="absolute top-4 right-4 bg-white/10 backdrop-blur-md text-white border border-white/20 p-2 rounded-full hover:bg-red-500 hover:border-red-500 transition-all transform hover:scale-105"
                       title="Remove Image"
                     >
                       ✕
                     </button>
                    )}
                  </div>
                )}
              </div>
            </div>

            {/* Controls */}
            {image && status !== AnalysisStatus.SCANNING && status !== AnalysisStatus.COMPLETE && (
              <div className="flex justify-center animate-fade-in">
                <button
                  onClick={handleScan}
                  className="bg-gradient-brand text-white font-bold text-lg py-4 px-12 rounded-full hover:brightness-110 transition-all shadow-lg hover:shadow-indigo-500/30 flex items-center gap-3 transform hover:-translate-y-1 active:translate-y-0"
                >
                  <Sparkles className="w-5 h-5 fill-current" />
                  Run Analysis
                </button>
              </div>
            )}

            {status === AnalysisStatus.SCANNING && (
              <div className="bg-white border border-indigo-100 p-8 rounded-2xl shadow-lg flex flex-col items-center justify-center animate-pulse-slow">
                <Loader2 className="w-10 h-10 text-indigo-600 animate-spin mb-4" />
                <h3 className="text-xl font-bold text-gray-800">Processing Evidence...</h3>
                <p className="text-gray-500">Scanning for diffusion artifacts and geometric inconsistencies.</p>
              </div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-100 text-red-600 p-4 rounded-xl flex items-center gap-3 animate-fade-in">
                <AlertTriangle className="w-5 h-5" /> 
                <span className="font-medium">{error}</span>
              </div>
            )}

            {/* Results Section */}
            {status === AnalysisStatus.COMPLETE && result && (
              <div className="bg-white rounded-3xl shadow-xl shadow-gray-200/50 border border-white overflow-hidden animate-fade-in-up">
                
                <div className="p-8 space-y-8">
                  <div className="flex flex-col md:flex-row items-center gap-6 text-center md:text-left">
                    <div className={`p-6 rounded-full shadow-inner ${result.isAi ? 'bg-red-50 text-red-500' : 'bg-emerald-50 text-emerald-500'} transition-transform hover:scale-105 duration-300`}>
                      {result.isAi ? <AlertTriangle className="w-12 h-12" /> : <CheckCircle className="w-12 h-12" />}
                    </div>
                    <div className="flex-1 w-full">
                      <h3 className={`text-3xl font-extrabold mb-1 ${result.isAi ? 'text-red-500' : 'text-emerald-500'}`}>
                        {result.isAi ? 'AI GENERATED' : 'AUTHENTIC MEDIA'}
                      </h3>
                      <p className="text-gray-400 text-sm font-medium tracking-wider uppercase mb-4">Detection Verdict</p>
                      
                      <div className="relative pt-1">
                        <div className="flex mb-2 items-center justify-between">
                          <div>
                            <span className="text-xs font-semibold inline-block py-1 px-2 uppercase rounded-full text-indigo-600 bg-indigo-50">
                              Confidence
                            </span>
                          </div>
                          <div className="text-right">
                            <span className="text-xs font-bold inline-block text-indigo-600">
                              {result.confidence}%
                            </span>
                          </div>
                        </div>
                        <div className="overflow-hidden h-3 mb-4 text-xs flex rounded-full bg-indigo-50 shadow-inner">
                          <div 
                             style={{ width: `${result.confidence}%` }} 
                             className={`shadow-none flex flex-col text-center whitespace-nowrap text-white justify-center ${result.isAi ? 'bg-gradient-to-r from-red-400 to-red-600' : 'bg-gradient-to-r from-emerald-400 to-emerald-600'} transition-all duration-1000 ease-out`}
                          ></div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="bg-gradient-subtle p-6 rounded-2xl border border-indigo-100/50">
                    <h4 className="text-indigo-900 font-bold text-sm mb-3 uppercase tracking-wide flex items-center gap-2">
                        <FileSearch className="w-4 h-4" /> Forensic Summary
                    </h4>
                    <p className="text-indigo-800 leading-relaxed font-medium">{result.analysis}</p>
                  </div>

                  {result.artifacts.length > 0 && (
                    <div>
                      <h4 className="text-gray-900 font-bold text-sm mb-4 uppercase tracking-wide">Detected Artifacts</h4>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                        {result.artifacts.map((artifact, i) => (
                          <div key={i} className="flex items-center gap-3 text-sm font-medium text-gray-700 bg-gray-50 border border-gray-100 p-4 rounded-xl">
                            <span className="w-2 h-2 bg-red-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(239,68,68,0.6)]"></span>
                            {artifact}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
                {adConfig?.showAds && <div className="p-6 border-t border-gray-100 bg-gray-50/50"><AdUnit location="result" enabled={adConfig.resultAd} /></div>}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="hidden lg:block space-y-6 animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
             <div className="bg-white border border-gray-100 p-6 rounded-2xl shadow-lg shadow-gray-100/50">
               <h3 className="font-bold text-gray-900 mb-4 text-xs uppercase tracking-wider flex items-center gap-2">
                 <ImageIcon className="w-4 h-4 text-indigo-500" /> System Status
               </h3>
               <div className="space-y-4">
                 <div className="flex items-center justify-between text-sm p-3 bg-gray-50 rounded-lg">
                   <span className="text-gray-600">Engine</span>
                   <span className="flex items-center gap-2 text-emerald-600 font-bold text-xs">
                      Nano Banana 2.5
                   </span>
                 </div>
                 <div className="flex items-center justify-between text-sm p-3 bg-gray-50 rounded-lg">
                   <span className="text-gray-600">Status</span>
                   <span className="flex items-center gap-2 text-indigo-600 font-bold text-xs">
                     <span className="relative flex h-2 w-2">
                        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-indigo-400 opacity-75"></span>
                        <span className="relative inline-flex rounded-full h-2 w-2 bg-indigo-500"></span>
                      </span> 
                      Online
                   </span>
                 </div>
               </div>
             </div>
             
             {adConfig?.showAds && <AdUnit location="sidebar" enabled={adConfig.sidebarAd} />}
             
             <div className="bg-gradient-to-br from-indigo-500 to-purple-600 text-white p-6 rounded-2xl shadow-lg relative overflow-hidden">
                <div className="absolute top-0 right-0 -mt-4 -mr-4 w-24 h-24 bg-white/20 rounded-full blur-xl"></div>
                <h4 className="font-bold mb-2 text-sm relative z-10 flex items-center gap-2">
                    <Sparkles className="w-4 h-4" /> Pro Tip
                </h4>
                <p className="text-xs text-indigo-100 leading-relaxed relative z-10">
                  Look for inconsistent shadows and over-smooth textures. AI struggles with complex object interaction and text generation.
                </p>
             </div>
          </div>
        </div>
      </main>
    </div>
  );
};