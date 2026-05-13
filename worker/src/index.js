import emote_ids from './emote_ids.json';

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    const host = url.hostname;
    const path = url.pathname.slice(1);
    const search = url.search;
    const fullPathStr = path + search;

    // 1. Root redirect
    if (path === "") {
      const randomString = Array.from({ length: 16 }, () =>
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"[Math.floor(Math.random() * 36)]
      ).join('');
      return Response.redirect(`${url.protocol}//${host}/${randomString}`, 302);
    }

    // 2. Try specific emoji ID if path matches /emojis/123...
    const emojiMatch = path.match(/^emojis\/(\d+)(\.(png|gif|webp))?$/);
    if (emojiMatch) {
      const id = emojiMatch[1];
      const isAnimated = emojiMatch[3] === 'gif';
      let response = await fetchDiscordEmote(id, isAnimated);
      if (response.status === 200) return response;
    }

    // 3. Filter emotes based on subdomain
    // xn--5k8h is the punycode for "🔍" or similar specific characters.
    let availableEmotes = emote_ids;
    if (host.startsWith("xn--5k8h")) {
      availableEmotes = emote_ids.filter(e => e.animated === true);
      
      // Fallback if the JSON contains no animated emotes to avoid modulo by zero
      if (availableEmotes.length === 0) availableEmotes = emote_ids;
    }

    // 4. Deterministic "Random" based on path seed
    const seed = await getSeed(fullPathStr.slice(0, 8));
    const index = seed % availableEmotes.length;
    const emote = availableEmotes[index];
    
    return fetchDiscordEmote(emote.id, emote.animated, true, availableEmotes);
  }
};

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
