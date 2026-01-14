
export interface Insight {
  label: string;
  content: string | string[];
}

export interface ReportItem {
  id: string;
  title: string;
  summary: string;
  insights: Insight[];
  sourceUrl: string;
  category: 'competitor' | 'industry';
  date?: string;
}

export type TabType = 'competitor' | 'industry' | 'ai-analyst';
