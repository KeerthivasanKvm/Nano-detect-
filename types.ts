export interface ScanResult {
  id: string;
  timestamp: number;
  imageUrl: string;
  isAi: boolean;
  confidence: number;
  analysis: string;
  artifacts: string[];
}

export interface AdConfig {
  showAds: boolean;
  headerAd: boolean;
  sidebarAd: boolean;
  resultAd: boolean;
}

export enum AnalysisStatus {
  IDLE = 'IDLE',
  SCANNING = 'SCANNING',
  COMPLETE = 'COMPLETE',
  ERROR = 'ERROR'
}