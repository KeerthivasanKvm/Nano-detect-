import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ShieldCheck, Zap } from 'lucide-react';

export const Header: React.FC = () => {
  const location = useLocation();

  const isActive = (path: string) => location.pathname === path 
    ? 'text-indigo-600 bg-indigo-50 font-semibold' 
    : 'text-gray-600 hover:text-indigo-600 hover:bg-gray-50';

  return (
    <nav className="bg-white/80 backdrop-blur-md border-b border-gray-100 sticky top-0 z-50 transition-all duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-20">
          <div className="flex items-center gap-2">
            <Link to="/" className="flex items-center gap-2 group">
              <div className="relative">
                <div className="absolute inset-0 bg-gradient-brand rounded-full blur opacity-20 group-hover:opacity-40 transition-opacity"></div>
                <ShieldCheck className="w-9 h-9 text-indigo-600 relative z-10" />
              </div>
              <div className="flex flex-col">
                <span className="font-sans font-extrabold text-2xl tracking-tight text-transparent bg-clip-text bg-gradient-brand leading-none">
                  NANO DETECT
                </span>
                <span className="text-[10px] uppercase tracking-widest text-gray-500 font-bold flex items-center gap-1">
                   <Zap className="w-3 h-3 text-amber-500" /> AI Forensics
                </span>
              </div>
            </Link>
          </div>
          <div className="hidden md:block">
            <div className="ml-10 flex items-center space-x-2">
              <Link to="/" className={`px-5 py-2.5 rounded-full text-sm transition-all ${isActive('/')}`}>
                Home
              </Link>
              <Link to="/scan" className={`px-5 py-2.5 rounded-full text-sm transition-all ${isActive('/scan')}`}>
                Scanner Tool
              </Link>
              {/* Admin link hidden from regular users */}
            </div>
          </div>
        </div>
      </div>
    </nav>
  );
};