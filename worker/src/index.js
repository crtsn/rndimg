import emote_ids from './emote_ids.json';
import audioAssets from './audio_assets.json';
import { ArrayBufferTarget, Muxer } from 'webm-muxer';
import { dictionary } from 'cmu-pronouncing-dictionary';

const AUDIO_HOSTS = new Set(['xn--dv8h', 'xn--k18h', 'xn--pp8h']);
const CAMERA_HOST = 'xn--5k8h';
const MAX_AUDIO_CHARACTERS = 24;
const FALLBACK_AUDIO_TEXT = 'i am a carrot';
const DIGIT_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
const TEEN_WORDS = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const TENS_WORDS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
const decodedSounds = new Map();
const carrotFrame = decodeBase64(audioAssets.video);
const graphemeTokens = Object.keys(audioAssets.audio)
  .filter(token => token.length > 1 && !token.startsWith('@') && !token.startsWith('#'))
  .sort((left, right) => right.length - left.length);
const wordSoundKeys = new Set(Object.keys(audioAssets.audio).filter(token => token.startsWith('@')));
const animatedEmotes = emote_ids.filter(emote => emote.animated);
const opusDecoderConfig = {
  decoderConfig: {
    codec: 'opus',
    sampleRate: 48000,
    numberOfChannels: 1,
    description: new Uint8Array([
      0x4f, 0x70, 0x75, 0x73, 0x48, 0x65, 0x61, 0x64,
      0x01, 0x01, 0x38, 0x01, 0x80, 0xbb, 0x00, 0x00,
      0x00, 0x00, 0x00
    ])
  }
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const host = url.hostname;
    const path = url.pathname.slice(1);
    const search = url.search;
    const fullPathStr = path + search;

    // 1. Letter-by-letter audio subdomain
    if (host.split('.').some(label => AUDIO_HOSTS.has(label))) {
      if (url.protocol === 'http:') {
        url.protocol = 'https:';
        return Response.redirect(url.toString(), 302);
      }
      return serveLetterVideo(request, url, path, ctx);
    }

    // 2. Root redirect
    if (path === "") {
      const randomString = Array.from({ length: 16 }, () =>
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[Math.floor(Math.random() * 36)]
      ).join('');
      return Response.redirect(`${url.protocol}//${host}/${randomString}`, 302);
    }

    // 3. Try specific emoji ID if path matches /emojis/123...
    const emojiMatch = path.match(/^emojis\/(\d+)(\.(png|gif|webp))?$/);
    if (emojiMatch) {
      const id = emojiMatch[1];
      const isAnimated = emojiMatch[3] === 'gif';
      let response = await fetchDiscordEmote(id, isAnimated);
      if (response.status === 200) return response;
    }

    const availableEmotes = host.split('.').includes(CAMERA_HOST) ? animatedEmotes : emote_ids;

    // 4. Deterministic "Random" based on path seed
    const seed = await getSeed(fullPathStr.slice(0, 8));
    const index = seed % availableEmotes.length;
    const emote = availableEmotes[index];
    
    return fetchDiscordEmote(emote.id, emote.animated, true, availableEmotes);
  }
};

async function serveLetterVideo(request, url, path, ctx) {
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    return new Response('Method not allowed', {
      status: 405,
      headers: { 'Allow': 'GET, HEAD' }
    });
  }

  let input;
  try {
    input = decodeURIComponent(path.replace(/\.(?:webm|gif|webp|png|jpe?g)$/i, ''));
  } catch {
    input = '';
  }

  const characters = Array.from(input);
  const text = characters.length === 0
    ? FALLBACK_AUDIO_TEXT
    : characters
      .slice(0, MAX_AUDIO_CHARACTERS)
      .map(character => /[a-z0-9]/i.test(character) ? character.toLowerCase() : ' ')
      .join('');

  const cacheKey = new Request(`${url.origin}/${encodeURIComponent(text)}.webm?audio-version=13`);
  const cached = await caches.default.match(cacheKey);
  if (cached) {
    return respondWithVideo(request, await cached.arrayBuffer(), cached.headers);
  }

  const buffer = buildLetterVideo(text);
  const headers = new Headers({
    'Accept-Ranges': 'bytes',
    'Cache-Control': 'public, max-age=300',
    'Content-Disposition': 'inline; filename="carrot-says.webm"',
    'Content-Length': String(buffer.byteLength),
    'Content-Type': 'video/webm',
    'X-Content-Type-Options': 'nosniff'
  });

  const response = new Response(buffer, { headers });
  ctx.waitUntil(caches.default.put(cacheKey, response.clone()));
  return respondWithVideo(request, buffer, headers);
}

function buildLetterVideo(text) {
  const muxer = new Muxer({
    target: new ArrayBufferTarget(),
    video: {
      codec: 'V_VP8',
      width: 512,
      height: 512,
      frameRate: 5
    },
    audio: {
      codec: 'A_OPUS',
      numberOfChannels: 1,
      sampleRate: 48000
    }
  });

  let timestamp = 0;
  let firstAudioPacket = true;
  for (const token of tokenizeSpeech(text)) {
    for (const packet of getSoundPackets(token)) {
      muxer.addAudioChunkRaw(packet, 'key', timestamp, firstAudioPacket ? opusDecoderConfig : undefined);
      firstAudioPacket = false;
      timestamp += 20000;
    }
  }

  const frameDuration = 200000;
  for (let frameTimestamp = 0; frameTimestamp < timestamp; frameTimestamp += frameDuration) {
    muxer.addVideoChunkRaw(carrotFrame, 'key', frameTimestamp);
  }
  muxer.addVideoChunkRaw(carrotFrame, 'key', timestamp);
  muxer.finalize();
  return muxer.target.buffer;
}

function tokenizeSpeech(text) {
  const tokens = [];

  for (const part of text.split(/( +)/)) {
    if (part === '') continue;

    if (part[0] === ' ') {
      tokens.push(...part);
      continue;
    }

    const wordKey = `@${part}`;
    if (wordSoundKeys.has(wordKey)) {
      tokens.push(wordKey);
      continue;
    }

    const pronunciation = dictionary[part];
    if (pronunciation) {
      const phonemes = pronunciation.split(' # ')[0].split(' ');
      tokens.push(...phonemes.map(phoneme => `#${phoneme.replace(/\d/g, '')}`));
      continue;
    }

    for (let index = 0; index < part.length;) {
      if (/\d/.test(part[index])) {
        const digits = part.slice(index).match(/^\d+/)[0];
        tokens.push(...tokenizeNumber(digits));
        index += digits.length;
        continue;
      }

      const grapheme = graphemeTokens.find(token => part.startsWith(token, index));
      const token = grapheme || part[index];
      tokens.push(token);
      index += token.length;
    }
  }

  return tokens;
}

function tokenizeNumber(digits) {
  const tokens = [];
  let index = 0;

  if (digits.length % 2 === 1) {
    tokens.push(`@${DIGIT_WORDS[Number(digits[0])]}`);
    index = 1;
  }

  for (; index < digits.length; index += 2) {
    const first = Number(digits[index]);
    const second = Number(digits[index + 1]);
    if (first === 0) {
      tokens.push('@zero', `@${DIGIT_WORDS[second]}`);
    } else if (first === 1) {
      tokens.push(`@${TEEN_WORDS[second]}`);
    } else {
      tokens.push(`@${TENS_WORDS[first]}`);
      if (second !== 0) tokens.push(`@${DIGIT_WORDS[second]}`);
    }
  }

  return tokens.flatMap((token, index) => index === tokens.length - 1 ? [token] : [token, ' ']);
}

function getSoundPackets(token) {
  let packets = decodedSounds.get(token);
  if (packets) return packets;

  const sound = audioAssets.audio[token];
  const data = decodeBase64(sound.data);
  let offset = 0;
  packets = sound.sizes.map(size => {
    const packet = data.subarray(offset, offset + size);
    offset += size;
    return packet;
  });
  decodedSounds.set(token, packets);
  return packets;
}

function decodeBase64(value) {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index++) {
    bytes[index] = binary.charCodeAt(index);
  }
  return bytes;
}

function respondWithVideo(request, buffer, sourceHeaders) {
  const headers = new Headers(sourceHeaders);
  const size = buffer.byteLength;
  const range = request.headers.get('Range');

  if (range) {
    const match = range.match(/^bytes=(\d*)-(\d*)$/);
    if (!match) {
      return new Response(null, {
        status: 416,
        headers: { 'Content-Range': `bytes */${size}` }
      });
    }

    let start = match[1] === '' ? Math.max(0, size - Number(match[2])) : Number(match[1]);
    let end = match[2] === '' ? size - 1 : Number(match[2]);
    end = Math.min(end, size - 1);

    if (!Number.isFinite(start) || !Number.isFinite(end) || start > end || start >= size) {
      return new Response(null, {
        status: 416,
        headers: { 'Content-Range': `bytes */${size}` }
      });
    }

    headers.set('Content-Length', String(end - start + 1));
    headers.set('Content-Range', `bytes ${start}-${end}/${size}`);
    return new Response(request.method === 'HEAD' ? null : buffer.slice(start, end + 1), {
      status: 206,
      headers
    });
  }

  headers.set('Content-Length', String(size));
  return new Response(request.method === 'HEAD' ? null : buffer, { headers });
}

/**
 * @param {string} id - Discord Emoji ID
 * @param {boolean} animated - Is animated
 * @param {boolean} allowFallback - Should we try a random emote if this one 404s?
 * @param {Array} pool - The filtered pool to pick from if fallback is needed
 */
async function fetchDiscordEmote(id, animated, allowFallback = false, pool = emote_ids) {
  const format = animated ? "gif" : "webp";
  const discordUrl = `https://cdn.discordapp.com/emojis/${id}.${format}?size=96&animated=${animated}`;

  let response = await fetch(discordUrl, {
    headers: {
      "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Accept": "image/gif,image/webp"
    }
  });

  if (!response.ok && allowFallback) {
    const randomEmote = pool[Math.floor(Math.random() * pool.length)];
    return fetchDiscordEmote(randomEmote.id, randomEmote.animated, false, pool);
  }

  const newResponse = new Response(response.body, response);
  newResponse.headers.set("Cache-Control", "no-cache, no-store, must-revalidate, public, max-age=0");
  newResponse.headers.set("Pragma", "no-cache");
  newResponse.headers.set("Expires", "0");

  return newResponse;
}

async function getSeed(str) {
  const msgUint8 = new TextEncoder().encode(str);
  const hashBuffer = await crypto.subtle.digest('SHA-1', msgUint8);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.slice(0, 4).reduce((acc, byte) => (acc << 8) + byte, 0) >>> 0;
}
