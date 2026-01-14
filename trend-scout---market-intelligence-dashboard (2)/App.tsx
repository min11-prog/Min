
import React, { useState, useEffect, useMemo } from 'react';
import { TabType } from './types';
import { MARKET_REPORTS } from './constants';
import { ReportCard } from './components/ReportCard';
import { GeminiAnalyst } from './components/GeminiAnalyst';
import { FilterBar } from './components/FilterBar';

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<TabType>('competitor');
  const [isScrolled, setIsScrolled] = useState(false);
  
  // Filtering States
  const [searchTerm, setSearchTerm] = useState('');
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const resetFilters = () => {
    setSearchTerm('');
    setStartDate('');
    setEndDate('');
  };

  const filteredReports = useMemo(() => {
    return MARKET_REPORTS.filter(report => {
      // 1. Category Filter
      if (report.category !== activeTab) return false;

      // 2. Keyword Filter
      const lowerSearch = searchTerm.toLowerCase();
      const matchesSearch = !searchTerm || 
        report.title.toLowerCase().includes(lowerSearch) || 
        report.summary.toLowerCase().includes(lowerSearch);
      
      if (!matchesSearch) return false;

      // 3. Date Range Filter
      if (report.date) {
        const reportDate = new Date(report.date).getTime();
        if (startDate && reportDate < new Date(startDate).getTime()) return false;
        if (endDate && reportDate > new Date(endDate).getTime()) return false;
      } else if (startDate || endDate) {
        // If report has no date but filter is set, we exclude it for consistency
        return false;
      }

      return true;
    });
  }, [activeTab, searchTerm, startDate, endDate]);

  return (
    <div className="min-h-screen flex flex-col font-sans">
      {/* Dynamic Header */}
      <header className={`sticky top-0 z-50 transition-all duration-300 ${
        isScrolled ? 'bg-white/90 backdrop-blur-md shadow-md py-3' : 'bg-gradient-header py-8 sm:py-12'
      }`}>
        <div className="container mx-auto px-4 text-center">
          <h1 className={`font-bold tracking-tight transition-all duration-300 ${
            isScrolled ? 'text-2xl text-slate-900' : 'text-4xl sm:text-6xl text-white'
          }`}>
            트렌드 스카우트
          </h1>
          {!isScrolled && (
            <p className="text-white/80 mt-4 text-lg sm:text-xl font-light">
              마켓 인텔리전스 및 산업 동향 리포트
            </p>
          )}
        </div>
      </header>

      <main className="flex-grow container mx-auto px-4 py-8 sm:py-12">
        {/* Navigation Tabs */}
        <div className="flex flex-wrap justify-center mb-10 gap-2 sm:gap-4">
          <button
            onClick={() => { setActiveTab('competitor'); resetFilters(); }}
            className={`px-6 py-3 rounded-2xl font-bold transition-all duration-300 shadow-sm ${
              activeTab === 'competitor'
                ? 'bg-blue-600 text-white scale-105'
                : 'bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            경쟁사 분석
          </button>
          <button
            onClick={() => { setActiveTab('industry'); resetFilters(); }}
            className={`px-6 py-3 rounded-2xl font-bold transition-all duration-300 shadow-sm ${
              activeTab === 'industry'
                ? 'bg-teal-600 text-white scale-105'
                : 'bg-white text-slate-600 hover:bg-slate-50'
            }`}
          >
            산업 트렌드
          </button>
          <button
            onClick={() => setActiveTab('ai-analyst')}
            className={`px-6 py-3 rounded-2xl font-bold transition-all duration-300 shadow-sm flex items-center gap-2 ${
              activeTab === 'ai-analyst'
                ? 'bg-indigo-600 text-white scale-105'
                : 'bg-white text-indigo-600 hover:bg-indigo-50 border border-indigo-100'
            }`}
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            AI 애널리스트
          </button>
        </div>

        {/* Content Area */}
        <div className="max-w-5xl mx-auto transition-all duration-500">
          {activeTab === 'ai-analyst' ? (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              <GeminiAnalyst />
            </div>
          ) : (
            <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
              {/* Filter Bar only for report tabs */}
              <FilterBar 
                searchTerm={searchTerm}
                setSearchTerm={setSearchTerm}
                startDate={startDate}
                setStartDate={setStartDate}
                endDate={endDate}
                setEndDate={setEndDate}
                onReset={resetFilters}
              />

              <div className="grid gap-8">
                {filteredReports.length > 0 ? (
                  filteredReports.map((report) => (
                    <ReportCard key={report.id} report={report} />
                  ))
                ) : (
                  <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-slate-200">
                    <p className="text-slate-400 font-medium">조건에 맞는 리포트를 찾을 수 없습니다.</p>
                    <button 
                      onClick={resetFilters}
                      className="mt-4 text-blue-600 hover:underline text-sm font-bold"
                    >
                      모든 필터 초기화
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </main>

      <footer className="bg-slate-900 text-slate-400 py-12 mt-12">
        <div className="container mx-auto px-4 flex flex-col sm:flex-row justify-between items-center gap-6">
          <div className="text-center sm:text-left">
            <h2 className="text-white font-bold text-xl mb-2">Trend Scout</h2>
            <p className="text-sm max-w-sm">실시간 시장 데이터와 AI 분석을 결합하여 비즈니스 통찰력을 제공하는 프리미엄 대시보드입니다.</p>
          </div>
          <div className="flex gap-8 text-sm">
            <a href="#" className="hover:text-white transition-colors">이용약관</a>
            <a href="#" className="hover:text-white transition-colors">개인정보처리방침</a>
            <a href="#" className="hover:text-white transition-colors">고객센터</a>
          </div>
          <div className="text-sm">
            © 2025 Trend Scout Inc. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
};

export default App;
