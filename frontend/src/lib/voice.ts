/** Voice and TTS helpers using the Web Speech API (no external services). */

let _voices: SpeechSynthesisVoice[] = []
let _voicesLoaded = false

function loadVoices() {
  if (!('speechSynthesis' in window)) return
  _voices = window.speechSynthesis.getVoices()
  _voicesLoaded = _voices.length > 0
}

if (typeof window !== 'undefined' && 'speechSynthesis' in window) {
  loadVoices()
  window.speechSynthesis.onvoiceschanged = loadVoices
}

/** True when speech synthesis is available. */
export function isSpeechSupported(): boolean {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

/** Pick a ru-RU voice when available, fallback to the browser default. */
export function pickRussianVoice(): SpeechSynthesisVoice | null {
  if (!_voicesLoaded) loadVoices()
  return (
    _voices.find((v) => v.lang?.toLowerCase().startsWith('ru')) ??
    _voices.find((v) => v.default) ??
    _voices[0] ??
    null
  )
}

export interface SpeakOptions {
  rate?: number
  pitch?: number
  volume?: number
  onend?: () => void
}

/** Speak a text using the given options. Replaces the current utterance. */
export function speak(text: string, options: SpeakOptions = {}) {
  if (!isSpeechSupported()) {
    options.onend?.()
    return
  }
  const synth = window.speechSynthesis
  synth.cancel()

  const utterance = new SpeechSynthesisUtterance(text)
  const voice = pickRussianVoice()
  if (voice) utterance.voice = voice
  utterance.lang = voice?.lang || 'ru-RU'
  utterance.rate = options.rate ?? 0.95
  utterance.pitch = options.pitch ?? 1
  utterance.volume = options.volume ?? 1
  if (options.onend) {
    utterance.onend = options.onend
  }
  synth.speak(utterance)
}

/** Stop any ongoing speech. */
export function stopSpeaking() {
  if (isSpeechSupported()) window.speechSynthesis.cancel()
}

/** A subtle UI click (used to unlock the audio context on first interaction). */
export function unlockAudio() {
  if (typeof window === 'undefined') return
  try {
    const ctx = new (window.AudioContext ||
      (window as any).webkitAudioContext)()
    ctx.resume()
  } catch {
    /* ignore */
  }
}
