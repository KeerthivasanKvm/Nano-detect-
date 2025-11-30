import React from 'react';
import { HashRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Header } from './components/Header';
import { Landing } from './pages/Landing';
import { Scanner } from './pages/Scanner';
import { Admin } from './pages/Admin';

const App: React.FC = () => {
  return (
    <HashRouter>
      <div className="flex flex-col min-h-screen bg-brand-light font-sans selection:bg-blue-100 selection:text-blue-900">
        <Header />
        <div className="flex-grow">
          <Routes>
            <Route path="/" element={<Landing />} />
            <Route path="/scan" element={<Scanner />} />
            <Route path="/admin" element={<Admin />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
        <footer className="bg-white border-t border-gray-200 py-10 text-center text-gray-500 text-sm">
          <p className="font-medium text-gray-900">© 2024 NANO DETECT</p>
          <p className="mt-2 text-xs text-gray-400">Powered by Google Gemini Nano • Enterprise Forensic Suite</p>
        </footer>
      </div>
    </HashRouter>
  );
};

export default App;