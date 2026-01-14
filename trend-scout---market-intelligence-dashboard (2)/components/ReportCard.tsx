
import React from 'react';
import { ReportItem } from '../types';

interface Props {
  report: ReportItem;
}

export const ReportCard: React.FC<Props> = ({ report }) => {
  return (
    <div className="bg-white rounded-xl shadow-md border border-slate-100 overflow-hidden hover:shadow-lg transition-all duration-300">
      <div className="p-6">
        <div className="flex flex-col sm:flex-row justify-between items-start mb-4 gap-2">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-1">
              <span className={`px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider rounded ${
                report.category === 'competitor' ? 'bg-blue-100 text-blue-600' : 'bg-teal-100 text-teal-600'
              }`}>
                {report.category === 'competitor' ? '경쟁사' : '산업 트렌드'}
              </span>
              {report.date && (
                <span className="text-xs text-slate-400 font-medium">{report.date}</span>
              )}
            </div>
            <h3 className="text-xl font-bold text-slate-800 leading-snug">{report.title}</h3>
          </div>
        </div>
        
        <div className="mb-6">
          <p className="text-slate-600 leading-relaxed text-sm sm:text-base">
            <span className="font-bold text-slate-900 block mb-1">요약:</span>
            {report.summary}
          </p>
        </div>

        <div className="overflow-x-auto border rounded-lg">
          <table className="w-full text-sm text-left border-collapse">
            <thead className="bg-slate-50 border-b">
              <tr>
                <th className="px-4 py-2 font-semibold text-slate-700 w-32">항목</th>
                <th className="px-4 py-2 font-semibold text-slate-700">내용</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {report.insights.map((insight, idx) => (
                <tr key={idx}>
                  <td className="px-4 py-3 align-top font-bold text-slate-900 bg-slate-50/50">{insight.label}</td>
                  <td className="px-4 py-3 text-slate-600">
                    {Array.isArray(insight.content) ? (
                      <ul className="list-disc pl-4 space-y-2">
                        {insight.content.map((item, i) => (
                          <li key={i}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      insight.content
                    )}
                  </td>
                </tr>
              ))}
              <tr>
                <td className="px-4 py-3 font-bold text-slate-900 bg-slate-50/50">출처</td>
                <td className="px-4 py-3">
                  <a 
                    href={report.sourceUrl} 
                    target="_blank" 
                    rel="noopener noreferrer" 
                    className="text-blue-500 hover:text-blue-700 underline truncate block max-w-xs sm:max-w-md"
                  >
                    {report.sourceUrl}
                  </a>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
