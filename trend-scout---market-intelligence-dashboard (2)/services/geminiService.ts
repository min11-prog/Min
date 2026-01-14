
import { GoogleGenAI, Type } from "@google/genai";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY || '' });

export const getTrendAnalysis = async (query: string, context: string) => {
  try {
    const response = await ai.models.generateContent({
      model: 'gemini-3-flash-preview',
      contents: `Context: ${context}\n\nQuestion: ${query}`,
      config: {
        systemInstruction: "You are a professional market analyst for Trend Scout. Analyze the provided market data and answer the user's question with strategic depth. Keep the tone professional, objective, and insightful in Korean.",
        temperature: 0.7,
      },
    });
    return response.text || "분석 결과를 가져올 수 없습니다.";
  } catch (error) {
    console.error("Gemini API Error:", error);
    return "API 호출 중 오류가 발생했습니다. 나중에 다시 시도해 주세요.";
  }
};
