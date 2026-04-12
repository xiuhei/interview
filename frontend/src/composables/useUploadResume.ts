import { storeToRefs } from "pinia";

import { useResumeStore } from "@/stores/resume";

export function useUploadResume() {
  const store = useResumeStore();
  const { library, libraryLoading, loading, parsing, selectedResume, selectedSummary } = storeToRefs(store);

  return {
    loading,
    libraryLoading,
    parsing,
    library,
    resume: selectedResume,
    summary: selectedSummary,
    handleUpload: store.uploadAndParse,
    loadLibrary: store.loadLibrary,
    selectResume: store.selectResume,
    selectResumeById: store.selectResumeById,
    clearSelection: store.clearSelection,
  };
}
