import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  PRE_BUFFER_CHUNKS,
  PRE_BUFFER_MS,
  SILENCE_TIMEOUT_MS,
  accumulateTranscript,
  isFatalRecognitionError,
  decodeBase64ToArrayBuffer,
  waitForQueuedChunk,
  pollUntil,
} from '../voice-utils';

// Characterization net for the useVoice.js -> voice-utils.js extraction
// (CQ wave 9). Pins the exact pure-helper behavior the verbatim move must
// preserve: transcript accumulation/live-display rules, the fatal-vs-benign
// recognition error split, base64 mp3 decoding, the chunk-wait retry window,
// and the playback-done polling loop. Timing constants are pinned because
// the audio pipeline's buffering behavior depends on them.

describe('voice timing constants', () => {
  it('pins the buffering/silence values useVoice was built around', () => {
    expect(PRE_BUFFER_CHUNKS).toBe(5);
    expect(PRE_BUFFER_MS).toBe(2000);
    expect(SILENCE_TIMEOUT_MS).toBe(4000);
  });
});

// Minimal stand-in for a SpeechRecognitionEvent: results is an array of
// result lists, each with [0].transcript and an isFinal flag.
function makeEvent(resultIndex, results) {
  return {
    resultIndex,
    results: results.map(([text, isFinal]) => {
      const r = [{ transcript: text }];
      r.isFinal = isFinal;
      return r;
    }),
  };
}

describe('accumulateTranscript', () => {
  it('appends final results to the accumulated transcript with a space', () => {
    const out = accumulateTranscript('hello', makeEvent(0, [['world', true]]));
    expect(out.accumulated).toBe('hello world');
    expect(out.live).toBe('hello world');
  });

  it('does not prepend a space when accumulated is empty', () => {
    const out = accumulateTranscript('', makeEvent(0, [['hi there', true]]));
    expect(out.accumulated).toBe('hi there');
    expect(out.live).toBe('hi there');
  });

  it('shows interim results in live but not in accumulated', () => {
    const out = accumulateTranscript('so far', makeEvent(0, [['maybe', false]]));
    expect(out.accumulated).toBe('so far');
    expect(out.live).toBe('so far maybe');
  });

  it('concatenates multiple final results without separators (verbatim browser behavior)', () => {
    const out = accumulateTranscript('', makeEvent(0, [['ab', true], ['cd', true]]));
    expect(out.accumulated).toBe('abcd');
  });

  it('starts reading at resultIndex, skipping already-processed results', () => {
    const out = accumulateTranscript('', makeEvent(1, [['old', true], ['new', true]]));
    expect(out.accumulated).toBe('new');
  });

  it('trims the live transcript', () => {
    const out = accumulateTranscript('', makeEvent(0, [[' padded ', false]]));
    expect(out.live).toBe('padded');
    expect(out.accumulated).toBe('');
  });
});

describe('isFatalRecognitionError', () => {
  it('treats no-speech and aborted as benign (continuous-mode noise)', () => {
    expect(isFatalRecognitionError('no-speech')).toBe(false);
    expect(isFatalRecognitionError('aborted')).toBe(false);
  });

  it('treats permission/network errors as fatal', () => {
    expect(isFatalRecognitionError('not-allowed')).toBe(true);
    expect(isFatalRecognitionError('service-not-allowed')).toBe(true);
    expect(isFatalRecognitionError('network')).toBe(true);
  });
});

describe('decodeBase64ToArrayBuffer', () => {
  it('decodes base64 into the original bytes', () => {
    // btoa of bytes [72, 105, 33] = "Hi!"
    const buffer = decodeBase64ToArrayBuffer(btoa('Hi!'));
    expect(buffer).toBeInstanceOf(ArrayBuffer);
    expect(Array.from(new Uint8Array(buffer))).toEqual([72, 105, 33]);
  });

  it('handles binary (non-ASCII) byte values', () => {
    const bytes = [0, 255, 128, 7];
    const base64 = btoa(String.fromCharCode(...bytes));
    expect(Array.from(new Uint8Array(decodeBase64ToArrayBuffer(base64)))).toEqual(bytes);
  });
});

describe('waitForQueuedChunk', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('resolves true as soon as a chunk arrives', async () => {
    let queueLength = 0;
    const promise = waitForQueuedChunk({
      getQueueLength: () => queueLength,
      isStreamDone: () => false,
    });
    queueLength = 1;
    await vi.advanceTimersByTimeAsync(500);
    await expect(promise).resolves.toBe(true);
  });

  it('gives up after 2 retries (1s) when the stream is already done', async () => {
    const promise = waitForQueuedChunk({
      getQueueLength: () => 0,
      isStreamDone: () => true,
    });
    await vi.advanceTimersByTimeAsync(1000);
    await expect(promise).resolves.toBe(false);
  });

  it('waits up to 20 retries (10s) while the stream is still sending', async () => {
    let resolved = null;
    waitForQueuedChunk({
      getQueueLength: () => 0,
      isStreamDone: () => false,
    }).then(v => { resolved = v; });
    await vi.advanceTimersByTimeAsync(9500);
    expect(resolved).toBe(null); // still waiting at 9.5s
    await vi.advanceTimersByTimeAsync(500);
    expect(resolved).toBe(false); // gave up at 10s
  });

  it('stops retrying early when the stream finishes mid-wait', async () => {
    let streamDone = false;
    let resolved = null;
    waitForQueuedChunk({
      getQueueLength: () => 0,
      isStreamDone: () => streamDone,
    }).then(v => { resolved = v; });
    await vi.advanceTimersByTimeAsync(500);
    streamDone = true;
    await vi.advanceTimersByTimeAsync(500);
    expect(resolved).toBe(false);
  });
});

describe('pollUntil', () => {
  beforeEach(() => { vi.useFakeTimers(); });
  afterEach(() => { vi.useRealTimers(); });

  it('resolves immediately when already done', async () => {
    let resolved = false;
    pollUntil(() => true).then(() => { resolved = true; });
    await vi.advanceTimersByTimeAsync(0);
    expect(resolved).toBe(true);
  });

  it('polls every 200ms until done', async () => {
    let done = false;
    let resolved = false;
    pollUntil(() => done).then(() => { resolved = true; });
    await vi.advanceTimersByTimeAsync(600);
    expect(resolved).toBe(false);
    done = true;
    await vi.advanceTimersByTimeAsync(200);
    expect(resolved).toBe(true);
  });

  it('gives up after maxChecks (default 75 checks = ~15s)', async () => {
    let resolved = false;
    pollUntil(() => false).then(() => { resolved = true; });
    await vi.advanceTimersByTimeAsync(75 * 200);
    expect(resolved).toBe(false); // check 75: checks > 75 is still false
    await vi.advanceTimersByTimeAsync(200);
    expect(resolved).toBe(true); // check 76 exceeds the cap
  });
});
