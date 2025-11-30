import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Eye, Lock, Sparkles, Zap } from 'lucide-react';
import { AdConfig } from '../types';
import { AdUnit } from '../components/AdUnit';
import { getAdConfig } from '../services/storageService';

export const Landing: React.FC = () => {
  const [adConfig, setAdConfig] = React.useState<AdConfig | null>(null);

  React.useEffect(() => {
    getAdConfig().then(setAdConfig);
  }, []);

  return (
    <div className="min-h-screen bg-white">
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        {/* Background blobs */}
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden z-0 opacity-30">
            <div className="absolute top-[-10%] right-[-5%] w-[500px] h-[500px] rounded-full bg-purple-300 blur-[100px] animate-float"></div>
            <div className="absolute bottom-[-10%] left-[-10%] w-[600px] h-[600px] rounded-full bg-indigo-300 blur-[120px] animate-float" style={{animationDelay: '2s'}}></div>
            <div className="absolute top-[20%] left-[20%] w-[300px] h-[300px] rounded-full bg-pink-300 blur-[80px] animate-float" style={{animationDelay: '4s'}}></div>
        </div>

        <div className="max-w-7xl mx-auto relative z-10">
          <div className="pb-8 sm:pb-16 md:pb-20 lg:pb-28 xl:pb-32 pt-20 px-4 sm:px-6 lg:px-8">
            <main className="mt-10 mx-auto max-w-4xl sm:mt-12 md:mt-16 lg:mt-20 xl:mt-28">
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-50 border border-indigo-100 text-indigo-600 text-sm font-semibold mb-6 animate-fade-in-up">
                    <Sparkles className="w-4 h-4" />
                    <span>Powered by Gemini Nano 2.5</span>
                </div>
                <h1 className="text-4xl tracking-tight font-extrabold text-gray-900 sm:text-5xl md:text-6xl animate-fade-in-up">
                  <span className="block">Detect the</span>{' '}
                  <span className="block text-transparent bg-clip-text bg-gradient-brand">Invisible</span>
                </h1>
                <p className="mt-3 text-base text-gray-500 sm:mt-5 sm:text-lg sm:max-w-2xl sm:mx-auto md:mt-5 md:text-xl animate-fade-in-up" style={{ animationDelay: '0.1s' }}>
                  A next-generation forensic tool. We use advanced AI to analyze digital imagery for synthetic artifacts, warped geometry, and diffusion patterns that the human eye misses.
                </p>
                <div className="mt-8 sm:mt-10 flex justify-center animate-fade-in-up" style={{ animationDelay: '0.2s' }}>
                  <div className="rounded-full shadow-lg shadow-indigo-200">
                    <Link
                      to="/scan"
                      className="w-full flex items-center justify-center px-8 py-4 border border-transparent text-base font-bold rounded-full text-white bg-gradient-brand hover:brightness-110 md:text-lg md:px-10 transition-all hover:shadow-xl hover:-translate-y-1"
                    >
                      Start Scanning Now <ArrowRight className="ml-2 w-5 h-5" />
                    </Link>
                  </div>
                </div>
              </div>
            </main>
          </div>
        </div>
      </div>

      {adConfig?.showAds && (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-12 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
          <AdUnit location="header" enabled={adConfig.headerAd} />
        </div>
      )}

      {/* Feature Grid */}
      <div className="py-24 bg-gradient-to-b from-white to-indigo-50/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            <h2 className="text-sm font-bold text-transparent bg-clip-text bg-gradient-brand tracking-widest uppercase">Why Choose Nano Detect?</h2>
            <p className="mt-2 text-3xl leading-8 font-extrabold tracking-tight text-gray-900 sm:text-4xl">
              Colorful Insights. Solid Proof.
            </p>
          </div>

          <div className="mt-20">
            <div className="grid grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
              {[
                {
                  name: 'Nano Engine',
                  description: 'Powered by Google\'s latest multimodal models for ultra-fast processing.',
                  icon: Zap,
                  color: 'text-amber-500 bg-amber-50'
                },
                {
                  name: 'Visual Anomaly Check',
                  description: 'Detects impossible lighting, warped hands, and diffusion artifacts instantly.',
                  icon: Eye,
                  color: 'text-indigo-500 bg-indigo-50'
                },
                {
                  name: 'Secure & Private',
                  description: 'Your data is processed securely. We value privacy above all else.',
                  icon: Lock,
                  color: 'text-emerald-500 bg-emerald-50'
                },
              ].map((feature, idx) => (
                <div key={feature.name} className="relative bg-white p-8 rounded-2xl shadow-sm border border-gray-100 hover:shadow-xl hover:-translate-y-1 transition-all duration-300 animate-fade-in-up" style={{ animationDelay: `${0.4 + (idx * 0.1)}s` }}>
                  <div className={`absolute -top-6 left-8 flex items-center justify-center h-12 w-12 rounded-xl shadow-lg ${feature.color}`}>
                    <feature.icon className="h-6 w-6" aria-hidden="true" />
                  </div>
                  <p className="mt-4 text-xl font-bold text-gray-900">{feature.name}</p>
                  <p className="mt-2 text-base text-gray-500 leading-relaxed">{feature.description}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};