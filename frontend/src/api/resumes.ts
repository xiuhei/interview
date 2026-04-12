import client from "./client";
import type { ApiEnvelope, ResumeLibraryItem, ResumeRead, ResumeSummary } from "@/types/models";

export function fetchResumes() {
  return client.get<never, ApiEnvelope<ResumeLibraryItem[]>>("/resumes");
}

export async function uploadResume(file: File) {
  const formData = new FormData();
  formData.append("file", file);
  return client.post<FormData, ApiEnvelope<ResumeRead>>("/resumes/upload", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
}

export function parseResume(resumeId: number) {
  return client.post<never, ApiEnvelope<{ id: number; summary: ResumeSummary }>>(`/resumes/${resumeId}/parse`);
}

export function fetchResumeSummary(resumeId: number) {
  return client.get<never, ApiEnvelope<ResumeSummary>>(`/resumes/${resumeId}/summary`);
}
