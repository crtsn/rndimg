import emote_ids from './emote_ids.json';
import audioAssets from './audio_assets.json';
import speechWasm from './speech.wasm';
import createSpeechModule from './speech.js';
import { ArrayBufferTarget, Muxer } from 'webm-muxer';

const AUDIO_HOSTS = new Set(['xn--dv8h', 'xn--k18h', 'xn--pp8h']);
const CAMERA_HOST = 'xn--5k8h';
const MAX_AUDIO_CHARACTERS = 24;
const FALLBACK_AUDIO_TEXT = 'i am a carrot';
const ESPEAK_VOICE = 'en-us+klatt';
const PRONUNCIATION_OVERRIDES = { urmom: 'your mom' };
const DIGIT_WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine'];
const TEEN_WORDS = ['ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen'];
const TENS_WORDS = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety'];
const carrotFrame = decodeBase64(audioAssets.video);
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

let speechPromise = null;

function getSpeechModule() {
  if (!speechPromise) {
    speechPromise = createSpeechModule({
      instantiateWasm(imports, receiveInstance) {
        const instance = new WebAssembly.Instance(speechWasm, imports);
        receiveInstance(instance, speechWasm);
        return {};
      }
    }).then(speech => {
      if (speech._sp_init() < 0) {
        throw new Error('speech wasm init failed');
      }
      if (speech.ccall('sp_set_voice', 'number', ['string'], [ESPEAK_VOICE]) !== 0) {
        speech.ccall('sp_set_voice', 'number', ['string'], ['en']);
      }
      return speech;
    }).catch(error => {
      speechPromise = null;
      throw error;
    });
  }
  return speechPromise;
}

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const host = url.hostname;
    const path = url.pathname.slice(1);
    const search = url.search;
    const fullPathStr = path + search;

    // 1. Speech synthesis subdomain
    if (host.split('.').some(label => AUDIO_HOSTS.has(label))) {
      if (url.protocol === 'http:') {
        url.protocol = 'https:';
        return Response.redirect(url.toString(), 302);
      }
      return serveSpeechVideo(request, url, path, ctx);
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

async function serveSpeechVideo(request, url, path, ctx) {
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

  const cacheKey = new Request(`${url.origin}/${encodeURIComponent(text)}.webm?audio-version=14`);
  const cached = await caches.default.match(cacheKey);
  if (cached) {
    return respondWithVideo(request, await cached.arrayBuffer(), cached.headers);
  }

  const speechText = buildSpeechText(text);
  const buffer = await buildSpeechVideo(await getSpeechModule(), speechText);
  if (!buffer) {
    return new Response('speech synthesis failed', { status: 500 });
  }

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

function buildSpeechText(text) {
  return text
    .split(' ')
    .map(part => {
      if (part === '') return null;
      if (/^\d+$/.test(part)) return numberToWords(part).join(' ');
      return PRONUNCIATION_OVERRIDES[part] ?? part;
    })
    .filter(Boolean)
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim() || FALLBACK_AUDIO_TEXT;
}

function numberToWords(digits) {
  const words = [];
  let index = 0;

  if (digits.length % 2 === 1) {
    words.push(DIGIT_WORDS[Number(digits[0])]);
    index = 1;
  }

  for (; index < digits.length; index += 2) {
    const first = Number(digits[index]);
    const second = Number(digits[index + 1]);
    if (first === 0) {
      words.push('zero', DIGIT_WORDS[second]);
    } else if (first === 1) {
      words.push(TEEN_WORDS[second]);
    } else {
      words.push(TENS_WORDS[first]);
      if (second !== 0) words.push(DIGIT_WORDS[second]);
    }
  }

  return words;
}

async function buildSpeechVideo(speech, text) {
  let packetCount = speech.ccall('sp_synth', 'number', ['string'], [text]);
  if (packetCount <= 0 && text !== FALLBACK_AUDIO_TEXT) {
    packetCount = speech.ccall('sp_synth', 'number', ['string'], [FALLBACK_AUDIO_TEXT]);
  }
  if (packetCount <= 0) return null;

  const packetBytes = speech._sp_packet_bytes();
  const dataAddress = speech._sp_packet_data();
  const sizesAddress = speech._sp_packet_sizes();
  const packets = [];
  const sizes = new Int32Array(speech.HEAP32.buffer, sizesAddress, packetCount);
  let offset = 0;
  for (let index = 0; index < packetCount; index++) {
    packets.push(new Uint8Array(speech.HEAPU8.buffer, dataAddress + offset, sizes[index]).slice());
    offset += sizes[index];
  }

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
  for (let index = 0; index < packets.length; index++) {
    muxer.addAudioChunkRaw(packets[index], 'key', timestamp, index === 0 ? opusDecoderConfig : undefined);
    timestamp += 20000;
  }

  const frameDuration = 200000;
  for (let frameTimestamp = 0; frameTimestamp < timestamp; frameTimestamp += frameDuration) {
    muxer.addVideoChunkRaw(carrotFrame, 'key', frameTimestamp);
  }
  muxer.addVideoChunkRaw(carrotFrame, 'key', timestamp);
  muxer.finalize();
  return muxer.target.buffer;
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
