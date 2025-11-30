import { GoogleGenAI, Type } from "@google/genai";
import { ScanResult } from "../types";

const ai = new GoogleGenAI({ apiKey: process.env.API_KEY });

export const analyzeImage = async (base64Image: string, mimeType: string): Promise<Omit<ScanResult, 'id' | 'timestamp' | 'imageUrl'>> => {
  try {
    const prompt = `
      Act as a digital forensics expert. Analyze the provided image for signs of AI generation.
      Look for:
      - Inconsistent lighting or shadows.
      - Warped geometry (hands, eyes, architectural lines).
      - Text gibberish or nonsensical background details.
      - Over-smoothing or "plastic" skin textures.

      Return a JSON object with:
      - isAi: boolean (true if likely AI generated)
      - confidence: number (0 to 100)
      - analysis: string (A concise summary of findings, max 2 sentences)
      - artifacts: string[] (List of up to 4 specific visual artifacts found)
    `;

    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash-image',
      contents: {
        parts: [
          {
            inlineData: {
              data: base64Image,
              mimeType: mimeType
            }
          },
          { text: prompt }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            isAi: { type: Type.BOOLEAN },
            confidence: { type: Type.NUMBER },
            analysis: { type: Type.STRING },
            artifacts: {
              type: Type.ARRAY,
              items: { type: Type.STRING }
            }
          }
        }
      }
    });

    if (!response.text) {
      throw new Error("No response from AI");
    }

    const result = JSON.parse(response.text);
    return result;

  } catch (error) {
    console.error("Analysis failed:", error);
    throw new Error("Failed to analyze image. Please try again.");
  }
};