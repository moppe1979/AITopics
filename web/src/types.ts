export interface Article {
  id: number;
  title: string;
  url: string;
  publishedAt: string | null;
  fetchedAt: string;
  sourceId: string;
  source: string;
  summary: string | null;
  summaryKind: 'excerpt' | 'ai' | 'none';
  categories: string[];
  keywords: string[];
  importance: number;
  usagePoints: string | null;
}

export interface Source {
  id: string;
  name: string;
  url: string;
  enabled: boolean;
  lastFetchedAt: string | null;
  status: string | null;
  error: string | null;
}

export interface FetchLog {
  runAt: string;
  source: string;
  processed: number;
  success: number;
  failed: number;
  error: string | null;
}

export interface Dataset {
  generatedAt: string;
  lastRunAt: string | null;
  categories: string[];
  articles: Article[];
  sources: Source[];
  logs: FetchLog[];
}
