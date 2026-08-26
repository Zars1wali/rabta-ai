export function sanitizeReply(text: string): string {
  if (!text) return '';

  let cleaned = text;

  // 1. Remove markdown bold, italic, strikethrough: **text**, *text*, __text__, _text_, ~~text~~
  cleaned = cleaned.replace(/\*\*([^*]+)\*\*/g, '$1');
  cleaned = cleaned.replace(/__([^_]+)__/g, '$1');
  cleaned = cleaned.replace(/\*([^*]+)\*/g, '$1');
  cleaned = cleaned.replace(/(?<!\w)_([^_]+)_(?!\w)/g, '$1');
  cleaned = cleaned.replace(/~~([^~]+)~~/g, '$1');

  // 2. Remove code blocks and inline backticks: ```code```, `code`
  cleaned = cleaned.replace(/```[\s\S]*?```/g, '');
  cleaned = cleaned.replace(/`([^`]+)`/g, '$1');

  // 3. Remove markdown headers: # Header, ## Header
  cleaned = cleaned.replace(/^#{1,6}\s+(.+)$/gm, '$1');

  // 4. Remove markdown bullet points and numbered lists: - item, * item, 1. item
  cleaned = cleaned.replace(/^[\s]*[-*+]\s+/gm, '');
  cleaned = cleaned.replace(/^[\s]*\d+\.\s+/gm, '');

  // 5. Remove blockquotes: > quote
  cleaned = cleaned.replace(/^>\s+/gm, '');

  // 6. Limit emojis to at most 1 emoji in the entire reply
  cleaned = limitEmojis(cleaned, 1);

  // 7. Collapse multiple spaces and multiple empty lines
  cleaned = cleaned.replace(/[ \t]+/g, ' ');
  cleaned = cleaned.replace(/\n{3,}/g, '\n\n');

  return cleaned.trim();
}

/**
 * Retains up to `maxEmojis` emojis and strips any additional emojis.
 */
export function limitEmojis(text: string, maxEmojis = 1): string {
  // Regex matching unicode emojis
  const emojiRegex =
    /(\p{Extended_Pictographic}|\p{Emoji_Presentation}|\uFE0F|\u200D)+/gu;

  let emojiCount = 0;
  return text.replace(emojiRegex, (match) => {
    emojiCount++;
    if (emojiCount <= maxEmojis) {
      return match;
    }
    return '';
  });
}
