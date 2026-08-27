import { describe, it, expect, vi } from 'vitest';
import { DeepgramTranscriber } from '../src/channels/index.js';

describe('Deepgram Voice Note Processing & Europe-Tier Guard (WP-21)', () => {
  const sampleAudioBuffer = new Uint8Array([0, 1, 2, 3, 4]);

  it('resolves supported languages accurately', () => {
    const transcriber = new DeepgramTranscriber({ apiKey: 'dg_key_123' });
    expect(transcriber.resolveLanguage('pt-PT')).toBe('pt');
    expect(transcriber.resolveLanguage('en-US')).toBe('en');
    expect(transcriber.resolveLanguage('es-ES')).toBe('es');
    expect(transcriber.resolveLanguage('ur-PK')).toBe('ur');
    expect(transcriber.resolveLanguage(undefined)).toBe('pt');
  });

  it('transcribes audio buffer using Deepgram nova-3 model', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: {
          channels: [
            {
              alternatives: [
                {
                  transcript: 'Olá, gostaria de saber o preço do plano standard.',
                  confidence: 0.98
                }
              ]
            }
          ]
        },
        metadata: {
          duration: 3.5
        }
      })
    });

    const transcriber = new DeepgramTranscriber({
      apiKey: 'dg_key_123',
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await transcriber.transcribeAudio({
      audioBuffer: sampleAudioBuffer,
      mimetype: 'audio/ogg; codecs=opus',
      locale: 'pt-PT',
      tier: 'standard'
    });

    expect(res.ok).toBe(true);
    expect(res.transcript).toBe('Olá, gostaria de saber o preço do plano standard.');
    expect(res.confidence).toBe(0.98);
    expect(res.durationSeconds).toBe(3.5);

    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('https://api.deepgram.com/v1/listen?model=nova-3&smart_format=true&punctuate=true&language=pt'),
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({
          Authorization: 'Token dg_key_123'
        })
      })
    );
  });

  it('strictly enforces Europe-tier EU data residency guard by blocking non-EU endpoints', async () => {
    const mockFetch = vi.fn();
    const nonEuTranscriber = new DeepgramTranscriber({
      apiKey: 'dg_key_123',
      euResidentEndpoint: false, // NOT an EU-resident endpoint
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await nonEuTranscriber.transcribeAudio({
      audioBuffer: sampleAudioBuffer,
      mimetype: 'audio/ogg',
      locale: 'pt-PT',
      tier: 'europe' // Europe Tier!
    });

    expect(res.ok).toBe(false);
    expect(res.error).toBe('EU_DATA_RESIDENCY_CONSTRAINT');
    expect(res.userFacingFallback).toContain('União Europeia');
    expect(mockFetch).not.toHaveBeenCalled(); // Hard block — no network request outside EU!
  });

  it('allows Europe-tier audio processing when EU-resident endpoint is configured', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        results: {
          channels: [{ alternatives: [{ transcript: 'Audio transcrito em servidor EU.', confidence: 0.99 }] }]
        }
      })
    });

    const euTranscriber = new DeepgramTranscriber({
      apiKey: 'dg_key_123',
      euResidentEndpoint: true, // EU Resident!
      fetchFn: mockFetch as unknown as typeof fetch
    });

    const res = await euTranscriber.transcribeAudio({
      audioBuffer: sampleAudioBuffer,
      mimetype: 'audio/ogg',
      locale: 'pt-PT',
      tier: 'europe'
    });

    expect(res.ok).toBe(true);
    expect(res.transcript).toBe('Audio transcrito em servidor EU.');
    expect(mockFetch).toHaveBeenCalledWith(
      expect.stringContaining('https://api.eu.deepgram.com/v1/listen'),
      expect.anything()
    );
  });
});
