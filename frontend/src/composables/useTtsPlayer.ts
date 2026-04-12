import { ref } from "vue";

import { synthesizeSpeech } from "@/api/system";

interface PlayOptions {
  onStart?: () => void;
  onEnd?: () => void;
  onError?: (message: string) => void;
}

export function useTtsPlayer() {
  const isSpeaking = ref(false);
  let activeAudio: HTMLAudioElement | null = null;
  let currentObjectUrl: string | null = null;
  let requestId = 0;

  function cancel() {
    requestId += 1;
    if (activeAudio) {
      activeAudio.pause();
      activeAudio.src = "";
      activeAudio = null;
    }
    if (currentObjectUrl) {
      URL.revokeObjectURL(currentObjectUrl);
      currentObjectUrl = null;
    }
    isSpeaking.value = false;
  }

  async function speakText(text: string, options: PlayOptions = {}) {
    cancel();
    const currentRequestId = ++requestId;
    try {
      const response = await synthesizeSpeech(text);
      if (currentRequestId !== requestId) return;
      await playBase64(response.data.audio_base64, response.data.mime_type, options, currentRequestId);
    } catch (error) {
      if (currentRequestId !== requestId) return;
      isSpeaking.value = false;
      options.onError?.(error instanceof Error ? error.message : "语音播放失败");
    }
  }

  async function playBase64(
    audioBase64: string,
    mimeType = "audio/wav",
    options: PlayOptions = {},
    currentRequestId = ++requestId,
  ) {
    cancel();
    requestId = currentRequestId;
    try {
      const binary = window.atob(audioBase64);
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) {
        bytes[index] = binary.charCodeAt(index);
      }
      const blob = new Blob([bytes], { type: mimeType });
      currentObjectUrl = URL.createObjectURL(blob);
      const audio = new Audio(currentObjectUrl);
      activeAudio = audio;
      isSpeaking.value = true;
      options.onStart?.();
      await audio.play();
      await new Promise<void>((resolve, reject) => {
        audio.onended = () => resolve();
        audio.onerror = () => reject(new Error("audio_playback_failed"));
      });
      if (currentRequestId !== requestId) return;
      isSpeaking.value = false;
      options.onEnd?.();
    } catch (error) {
      if (currentRequestId !== requestId) return;
      isSpeaking.value = false;
      options.onError?.(error instanceof Error ? error.message : "语音播放失败");
    } finally {
      if (activeAudio) {
        activeAudio.src = "";
        activeAudio = null;
      }
      if (currentObjectUrl) {
        URL.revokeObjectURL(currentObjectUrl);
        currentObjectUrl = null;
      }
    }
  }

  return {
    isSpeaking,
    cancel,
    speakText,
    playBase64,
  };
}
