/**
 * The typing sound.
 *
 * Synthesised rather than sampled: a keystroke is a short noise burst through a
 * bandpass filter plus a low body thump, which is about eight lines of WebAudio
 * and no megabytes of audio files to load. It also means every keystroke can be
 * slightly different — filter frequency, decay and level all jitter — which is
 * what stops a long turn from sounding like a metronome.
 *
 * Kept deliberately quiet and dull. It is meant to sit under the reading, not to
 * be listened to.
 */

const MIN_GAP_MS = 34; // never more than ~29 keystrokes a second
const LOUD_CHARS = new Set([".", "!", "?", ",", ";", ":", "\n"]);

function randomBetween(low: number, high: number): number {
  return low + Math.random() * (high - low);
}

export class KeyboardSound {
  private ctx: AudioContext | null = null;
  private bus: GainNode | null = null;
  private noise: AudioBuffer | null = null;
  private lastAt = 0;
  private enabled = false;

  get isEnabled(): boolean {
    return this.enabled;
  }

  /**
   * Must be called from a user gesture the first time, or the browser will keep
   * the context suspended. Starting a debate is a click, so that is where it goes.
   */
  setEnabled(enabled: boolean): void {
    this.enabled = enabled;
    if (!enabled) return;
    const ctx = this.context();
    if (ctx && ctx.state === "suspended") void ctx.resume();
  }

  private context(): AudioContext | null {
    if (this.ctx) return this.ctx;
    const Ctor = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctor) return null;

    this.ctx = new Ctor();
    this.bus = this.ctx.createGain();
    this.bus.gain.value = 0.5;
    this.bus.connect(this.ctx.destination);

    // One second of noise, reused with a random offset per keystroke.
    const buffer = this.ctx.createBuffer(1, this.ctx.sampleRate, this.ctx.sampleRate);
    const data = buffer.getChannelData(0);
    for (let i = 0; i < data.length; i += 1) data[i] = Math.random() * 2 - 1;
    this.noise = buffer;

    return this.ctx;
  }

  /** Play one keystroke for `char`. Cheap enough to call per character. */
  press(char: string): void {
    if (!this.enabled) return;
    const ctx = this.context();
    if (!ctx || !this.noise || !this.bus || ctx.state !== "running") return;

    const now = ctx.currentTime;
    if (now * 1000 - this.lastAt < MIN_GAP_MS) return;
    this.lastAt = now * 1000;

    const space = char === " ";
    const punctuation = LOUD_CHARS.has(char);
    const level = space ? 0.075 : punctuation ? 0.06 : randomBetween(0.032, 0.05);
    const decay = space ? 0.055 : randomBetween(0.026, 0.042);

    // The click: filtered noise, gone in a few dozen milliseconds.
    const source = ctx.createBufferSource();
    source.buffer = this.noise;
    source.playbackRate.value = randomBetween(0.9, 1.1);

    const band = ctx.createBiquadFilter();
    band.type = "bandpass";
    band.frequency.value = space ? randomBetween(620, 820) : randomBetween(1250, 2450);
    band.Q.value = randomBetween(0.7, 1.2);

    const clickGain = ctx.createGain();
    clickGain.gain.setValueAtTime(level, now);
    clickGain.gain.exponentialRampToValueAtTime(0.0001, now + decay);

    source.connect(band).connect(clickGain).connect(this.bus);
    source.start(now, Math.random() * 0.9, decay + 0.01);

    // The body: a soft thump so it reads as a keycap bottoming out rather than a tick.
    const thump = ctx.createOscillator();
    thump.type = "sine";
    thump.frequency.setValueAtTime(space ? 96 : randomBetween(120, 170), now);

    const thumpGain = ctx.createGain();
    thumpGain.gain.setValueAtTime(level * 0.7, now);
    thumpGain.gain.exponentialRampToValueAtTime(0.0001, now + decay * 1.4);

    thump.connect(thumpGain).connect(this.bus);
    thump.start(now);
    thump.stop(now + decay * 1.5);
  }
}

export const keyboard = new KeyboardSound();
