import { defineStore } from "pinia";

import { fetchResumes, fetchResumeSummary, parseResume, uploadResume } from "@/api/resumes";
import type { ResumeLibraryItem, ResumeRead, ResumeSummary } from "@/types/models";

type ResumeSelection = ResumeLibraryItem | ResumeRead;

interface SelectResumeOptions {
  ensureParsed?: boolean;
  fetchSummary?: boolean;
}

function hasEmbeddedSummary(item: ResumeSelection | null): item is ResumeLibraryItem & { summary: ResumeSummary } {
  return Boolean(item && "summary" in item && item.summary);
}

export const useResumeStore = defineStore("resume", {
  state: () => ({
    library: [] as ResumeLibraryItem[],
    selectedResume: null as ResumeSelection | null,
    selectedSummary: null as ResumeSummary | null,
    loading: false,
    libraryLoading: false,
    parsing: false,
  }),
  actions: {
    updateLibraryItem(resumeId: number, patch: Partial<ResumeLibraryItem>) {
      const index = this.library.findIndex((item) => item.id === resumeId);
      if (index < 0) return;
      this.library.splice(index, 1, { ...this.library[index], ...patch });
    },
    syncSelectedResumeFromLibrary() {
      if (!this.selectedResume) return;
      const matched = this.library.find((item) => item.id === this.selectedResume?.id);
      if (!matched) return;
      this.selectedResume = matched;
      if (matched.summary) {
        this.selectedSummary = matched.summary;
      }
    },
    clearSelection() {
      this.selectedResume = null;
      this.selectedSummary = null;
    },
    async loadLibrary() {
      this.libraryLoading = true;
      try {
        const response = await fetchResumes();
        this.library = response.data;
        this.syncSelectedResumeFromLibrary();
        return response.data;
      } finally {
        this.libraryLoading = false;
      }
    },
    async parseResumeAndRefresh(resumeId: number) {
      this.parsing = true;
      try {
        const response = await parseResume(resumeId);
        const summary = response.data.summary;
        this.selectedSummary = summary;
        this.updateLibraryItem(resumeId, { status: "parsed", summary });
        await this.loadLibrary();
        this.syncSelectedResumeFromLibrary();
        return summary;
      } finally {
        this.parsing = false;
      }
    },
    async uploadAndParse(file: File) {
      this.loading = true;
      try {
        const uploaded = await uploadResume(file);
        this.selectedResume = uploaded.data;
        this.selectedSummary = null;
        const summary = await this.parseResumeAndRefresh(uploaded.data.id);
        const matched = this.library.find((item) => item.id === uploaded.data.id);
        this.selectedResume = matched || uploaded.data;
        this.selectedSummary = summary;
        return { resume: this.selectedResume, summary };
      } finally {
        this.loading = false;
      }
    },
    async selectResume(item: ResumeSelection, options: SelectResumeOptions = {}) {
      const { ensureParsed = false, fetchSummary = true } = options;

      this.selectedResume = item;

      if (ensureParsed && item.status !== "parsed") {
        return this.parseResumeAndRefresh(item.id);
      }

      if (hasEmbeddedSummary(item)) {
        this.selectedSummary = item.summary;
        return item.summary;
      }

      if (!fetchSummary || item.status !== "parsed") {
        this.selectedSummary = null;
        return null;
      }

      const response = await fetchResumeSummary(item.id);
      this.selectedSummary = response.data;
      this.updateLibraryItem(item.id, { status: "parsed", summary: response.data });
      this.syncSelectedResumeFromLibrary();
      return response.data;
    },
    async selectResumeById(resumeId: number, options: SelectResumeOptions = {}) {
      let item = this.library.find((entry) => entry.id === resumeId);

      if (!item && this.selectedResume?.id === resumeId) {
        return this.selectResume(this.selectedResume, options);
      }

      if (!item) {
        await this.loadLibrary();
        item = this.library.find((entry) => entry.id === resumeId);
      }

      if (!item) {
        throw new Error("未找到对应的简历记录");
      }

      return this.selectResume(item, options);
    },
  },
});
