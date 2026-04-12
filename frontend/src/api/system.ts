import client from "./client";
import type { ApiEnvelope, InterviewCapabilities } from "@/types/models";

export function fetchInterviewCapabilities() {
  return client.get<never, ApiEnvelope<InterviewCapabilities>>("/system/capabilities");
}

export function synthesizeSpeech(text: string) {
  return client.post<
    { text: string },
    ApiEnvelope<{ audio_base64: string; mime_type: string; model: string; voice: string }>
  >("/system/tts", { text });
}
