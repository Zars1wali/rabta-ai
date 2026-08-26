export interface ChunkingResult {
  bubbles: string[];
  delaysMs: number[];
}

/**
 * Splits reply text into conversational WhatsApp bubbles targeting ~280 characters.
 * Splits strictly along paragraph and sentence boundaries, falling back to word boundaries
 * only for oversized sentences.
 */
export function chunkReplyForWhatsApp(
  text: string,
  targetCharCount = 280,
  interMessageDelayMs = 1200
): ChunkingResult {
  const trimmed = text.trim();
  if (!trimmed) {
    return { bubbles: [], delaysMs: [] };
  }

  if (trimmed.length <= targetCharCount) {
    return {
      bubbles: [trimmed],
      delaysMs: [0]
    };
  }

  // 1. Break text into logical sentence / paragraph units
  const units = splitIntoSentences(trimmed);
  const bubbles: string[] = [];
  let currentBubble = '';

  for (const unit of units) {
    // If unit itself is longer than targetCharCount, split it by words
    if (unit.length > targetCharCount) {
      if (currentBubble.trim()) {
        bubbles.push(currentBubble.trim());
        currentBubble = '';
      }
      const wordChunks = splitOversizedSentence(unit, targetCharCount);
      bubbles.push(...wordChunks);
      continue;
    }

    const proposed = currentBubble ? `${currentBubble} ${unit}` : unit;
    if (proposed.length <= targetCharCount) {
      currentBubble = proposed;
    } else {
      if (currentBubble.trim()) {
        bubbles.push(currentBubble.trim());
      }
      currentBubble = unit;
    }
  }

  if (currentBubble.trim()) {
    bubbles.push(currentBubble.trim());
  }

  // Calculate delays: 0ms for first bubble, interMessageDelayMs (1200ms) for subsequent bubbles
  const delaysMs = bubbles.map((_, index) => (index === 0 ? 0 : interMessageDelayMs));

  return {
    bubbles,
    delaysMs
  };
}

function splitIntoSentences(text: string): string[] {
  // Matches punctuation followed by whitespace or linebreaks
  const sentences: string[] = [];
  const regex = /([^.!?\n]+[.!?]+|\n+)/g;

  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    const chunk = match[0].trim();
    if (chunk) {
      sentences.push(chunk);
    }
    lastIndex = regex.lastIndex;
  }

  const remainder = text.slice(lastIndex).trim();
  if (remainder) {
    sentences.push(remainder);
  }

  return sentences.length > 0 ? sentences : [text];
}

function splitOversizedSentence(sentence: string, targetCharCount: number): string[] {
  const words = sentence.split(/\s+/);
  const chunks: string[] = [];
  let current = '';

  for (const word of words) {
    if (word.length > targetCharCount) {
      if (current.trim()) {
        chunks.push(current.trim());
        current = '';
      }
      // Hard break oversized word
      for (let i = 0; i < word.length; i += targetCharCount) {
        chunks.push(word.slice(i, i + targetCharCount));
      }
      continue;
    }

    const proposed = current ? `${current} ${word}` : word;
    if (proposed.length <= targetCharCount) {
      current = proposed;
    } else {
      if (current.trim()) {
        chunks.push(current.trim());
      }
      current = word;
    }
  }

  if (current.trim()) {
    chunks.push(current.trim());
  }

  return chunks;
}
