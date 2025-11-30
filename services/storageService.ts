import { AdConfig, ScanResult } from "../types";

// Keys for LocalStorage
const DB_SCAN_KEY = 'nano_detect_scans';
const DB_AD_CONFIG_KEY = 'nano_detect_ad_config';

const defaultAdConfig: AdConfig = {
  showAds: true,
  headerAd: true,
  sidebarAd: false,
  resultAd: true,
};

// Simulate MongoDB Async Operations
export const saveScan = async (scan: ScanResult): Promise<void> => {
  const current = await getScans();
  const updated = [scan, ...current].slice(0, 50); // Keep last 50
  localStorage.setItem(DB_SCAN_KEY, JSON.stringify(updated));
};

export const getScans = async (): Promise<ScanResult[]> => {
  const data = localStorage.getItem(DB_SCAN_KEY);
  return data ? JSON.parse(data) : [];
};

export const getAdConfig = async (): Promise<AdConfig> => {
  const data = localStorage.getItem(DB_AD_CONFIG_KEY);
  return data ? JSON.parse(data) : defaultAdConfig;
};

export const updateAdConfig = async (config: AdConfig): Promise<void> => {
  localStorage.setItem(DB_AD_CONFIG_KEY, JSON.stringify(config));
};

export const clearHistory = async (): Promise<void> => {
  localStorage.removeItem(DB_SCAN_KEY);
}