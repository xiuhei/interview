import { ref } from "vue";

export function useRecorder() {
  const isRecording = ref(false);
  const mediaBlob = ref<Blob | null>(null);
  const errorMessage = ref("");
  let mediaRecorder: MediaRecorder | null = null;
  let mediaStream: MediaStream | null = null;
  let chunks: BlobPart[] = [];
  let stopResolver: ((blob: Blob | null) => void) | null = null;

  async function start() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaRecorder = new MediaRecorder(mediaStream);
      chunks = [];
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunks.push(event.data);
      };
      mediaRecorder.onstop = () => {
        const blob = chunks.length ? new Blob(chunks, { type: mediaRecorder?.mimeType || "audio/webm" }) : null;
        mediaBlob.value = blob;
        mediaStream?.getTracks().forEach((track) => track.stop());
        mediaStream = null;
        stopResolver?.(blob);
        stopResolver = null;
      };
      mediaRecorder.start();
      isRecording.value = true;
      errorMessage.value = "";
    } catch (error) {
      errorMessage.value = error instanceof Error ? error.message : "录音启动失败";
      cleanup();
    }
  }

  function stop(): Promise<Blob | null> {
    if (!mediaRecorder || mediaRecorder.state === "inactive") {
      isRecording.value = false;
      return Promise.resolve(mediaBlob.value);
    }
    isRecording.value = false;
    return new Promise((resolve) => {
      stopResolver = resolve;
      mediaRecorder?.stop();
    });
  }

  function reset() {
    mediaBlob.value = null;
    errorMessage.value = "";
  }

  function cleanup() {
    mediaRecorder = null;
    mediaStream?.getTracks().forEach((track) => track.stop());
    mediaStream = null;
    isRecording.value = false;
  }

  return { isRecording, mediaBlob, errorMessage, start, stop, reset, cleanup };
}