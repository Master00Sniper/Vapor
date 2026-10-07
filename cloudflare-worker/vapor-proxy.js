addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request));
});

// Known routes — reject everything else early
const KNOWN_ROUTES = ['/download/latest', '/telemetry', '/stats'];
// Repos the GitHub proxy may reach, lowercase (GitHub paths are case-insensitive).
// The repo moves from Master00Sniper to the gregmortonapps org (2026-10).
// Installed apps keep calling the OLD owner path, and after the move GitHub's
// release JSON hands out NEW-owner asset URLs, which the updater calls as-is,
// so both owners are allowed, before and after the move.
const ALLOWED_REPO_PREFIXES = ['/repos/master00sniper/vapor/', '/repos/gregmortonapps/vapor/'];

// Rate limit: max requests per IP for the public download endpoint
const DOWNLOAD_RATE_LIMIT = 30;   // requests per window
const DOWNLOAD_RATE_WINDOW = 3600; // 1 hour in seconds
const TELEMETRY_RATE_LIMIT = 120;   // events per IP per window; a real client sends a handful
const TELEMETRY_RATE_WINDOW = 3600; // 1 hour in seconds

// Cache TTL for /download/latest (avoids burning GitHub API calls)
const DOWNLOAD_CACHE_TTL = 600; // 10 minutes

async function handleRequest(request) {
  const url = new URL(request.url);

  // Handle CORS preflight requests
  if (request.method === 'OPTIONS') {
    return new Response(null, {
      status: 204,
      headers: {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, HEAD, POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Accept, User-Agent, X-Vapor-Auth, X-Stats-Key',
        'Access-Control-Max-Age': '86400'
      }
    });
  }

  // =========================================
  // Early rejection — unknown routes get 404
  // =========================================
  const isKnownRoute = KNOWN_ROUTES.includes(url.pathname);
  const isRepoProxy = ALLOWED_REPO_PREFIXES.some(p => url.pathname.toLowerCase().startsWith(p));
  if (!isKnownRoute && !isRepoProxy) {
    return new Response('Not Found', { status: 404 });
  }

  // =========================================
  // Download latest release (PUBLIC - no auth)
  // Cached + rate-limited to protect GitHub PAT
  // =========================================
  if (url.pathname === '/download/latest') {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return new Response('Method Not Allowed', { status: 405 });
    }

    // --- Per-IP rate limiting via KV ---
    const clientIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    const rateLimitKey = `ratelimit:download:${clientIP}`;
    const hitCount = parseInt(await TELEMETRY.get(rateLimitKey) || '0');
    if (hitCount >= DOWNLOAD_RATE_LIMIT) {
      return new Response('Too Many Requests', {
        status: 429,
        headers: { 'Retry-After': '3600' }
      });
    }
    await TELEMETRY.put(rateLimitKey, (hitCount + 1).toString(), {
      expirationTtl: DOWNLOAD_RATE_WINDOW
    });

    // --- Check Cloudflare Cache first ---
    const cacheKey = new Request(url.toString(), request);
    const cache = caches.default;
    let cachedResponse = await cache.match(cacheKey);
    if (cachedResponse) {
      return cachedResponse;
    }

    try {
      const releaseResponse = await fetch(
        'https://api.github.com/repos/Master00Sniper/Vapor/releases/latest',
        {
          headers: {
            'Authorization': `token ${GITHUB_PAT}`,
            'User-Agent': 'Vapor-Proxy/1.0',
            'Accept': 'application/vnd.github.v3+json'
          }
        }
      );

      if (!releaseResponse.ok) {
        return new Response('Failed to fetch release info', { status: 500 });
      }

      const release = await releaseResponse.json();

      // Find the .exe asset
      const asset = release.assets.find(a =>
        a.name.includes('Vapor') && a.name.endsWith('.exe')
      );

      if (!asset) {
        return new Response('No download found', { status: 404 });
      }

      // Build a cacheable redirect response
      const redirectResponse = new Response(null, {
        status: 302,
        headers: {
          'Location': asset.browser_download_url,
          'Cache-Control': `public, max-age=${DOWNLOAD_CACHE_TTL}`,
          'Access-Control-Allow-Origin': '*'
        }
      });

      // Store in Cloudflare edge cache
      await cache.put(cacheKey, redirectResponse.clone());

      return redirectResponse;
    } catch (e) {
      return new Response('Error fetching download', { status: 500 });
    }
  }

  // =========================================
  // Auth — SPLIT BY ROUTE (2026-09-01)
  // =========================================
  // One blanket gate used to guard both /telemetry (a WRITE) and /stats (a
  // read), so the stats dashboard on the public website had to carry a
  // write-capable key. Anyone reading that page could fabricate usage numbers.
  // /stats now also accepts a read-only key, so the website carries only that.
  // The write key still works everywhere, which is what keeps every installed
  // app reporting without an update.
  const authHeader = request.headers.get('X-Vapor-Auth') || '';
  const statsHeader = request.headers.get('X-Stats-Key') || '';
  const isWriteKey = authHeader && authHeader === VAPOR_AUTH_KEY;
  const isStatsKey = (typeof VAPOR_STATS_KEY !== 'undefined' && VAPOR_STATS_KEY)
    ? (statsHeader === VAPOR_STATS_KEY || authHeader === VAPOR_STATS_KEY)
    : false;
  const allowed = url.pathname === '/stats' ? (isWriteKey || isStatsKey) : isWriteKey;
  if (!allowed) {
    return new Response('Unauthorized', { status: 401 });
  }

  // =========================================
  // Telemetry endpoint
  // =========================================
  if (url.pathname === '/telemetry' && request.method === 'POST') {
    // Per-IP cap — see TELEMETRY_RATE_LIMIT. Silently accepted (204) rather
    // than 429'd: a real client must never retry-storm because it hit a cap,
    // and a forger gets no signal about where the limit is.
    const tIP = request.headers.get('CF-Connecting-IP') || 'unknown';
    const tKey = `ratelimit:telemetry:${tIP}`;
    const tHits = parseInt(await TELEMETRY.get(tKey) || '0');
    if (tHits >= TELEMETRY_RATE_LIMIT) {
      return new Response(null, { status: 204 });
    }
    await TELEMETRY.put(tKey, (tHits + 1).toString(), { expirationTtl: TELEMETRY_RATE_WINDOW });
    try {
      const data = await request.json();
      const { event, version, os, install_id } = data;

      if (!event || !install_id) {
        return new Response('Missing required fields', { status: 400 });
      }

      // Use Pacific time instead of UTC
      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });

      // Track daily active users (unique install_ids per day)
      const dauKey = `dau:${today}`;
      const existingDAU = await TELEMETRY.get(dauKey, { type: 'json' }) || [];
      if (!existingDAU.includes(install_id)) {
        existingDAU.push(install_id);
        await TELEMETRY.put(dauKey, JSON.stringify(existingDAU), {
          expirationTtl: 60 * 60 * 24 * 90
        });
      }

      // Track total events per day
      const eventKey = `events:${today}:${event}`;
      const eventCount = parseInt(await TELEMETRY.get(eventKey) || '0') + 1;
      await TELEMETRY.put(eventKey, eventCount.toString(), {
        expirationTtl: 60 * 60 * 24 * 90
      });

      // Track version distribution
      if (version) {
        const versionKey = `version:${today}:${version}`;
        const versionCount = parseInt(await TELEMETRY.get(versionKey) || '0') + 1;
        await TELEMETRY.put(versionKey, versionCount.toString(), {
          expirationTtl: 60 * 60 * 24 * 90
        });
      }

      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        }
      });
    } catch (e) {
      return new Response('Error processing telemetry', { status: 500 });
    }
  }

  // =========================================
  // Stats endpoint (check your usage)
  // =========================================
  if (url.pathname === '/stats') {
    try {
      // Use Pacific time instead of UTC
      const today = new Date().toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
      const dau = await TELEMETRY.get(`dau:${today}`, { type: 'json' }) || [];
      const starts = await TELEMETRY.get(`events:${today}:app_start`) || '0';
      const heartbeats = await TELEMETRY.get(`events:${today}:heartbeat`) || '0';

      // Calculate WAU and MAU by collecting unique install_ids across days
      const wauSet = new Set(dau);
      const mauSet = new Set(dau);
      const todayDate = new Date(today + 'T12:00:00-08:00');

      for (let i = 1; i < 30; i++) {
        const d = new Date(todayDate);
        d.setDate(d.getDate() - i);
        const dateStr = d.toLocaleDateString('en-CA', { timeZone: 'America/Los_Angeles' });
        const dayUsers = await TELEMETRY.get(`dau:${dateStr}`, { type: 'json' }) || [];
        dayUsers.forEach(id => {
          mauSet.add(id);
          if (i < 7) wauSet.add(id);
        });
      }

      return new Response(JSON.stringify({
        date: today,
        daily_active_users: dau.length,
        weekly_active_users: wauSet.size,
        monthly_active_users: mauSet.size,
        app_starts: parseInt(starts),
        heartbeats: parseInt(heartbeats)
      }, null, 2), {
        status: 200,
        headers: {
          'Content-Type': 'application/json',
          'Access-Control-Allow-Origin': '*'
        }
      });
    } catch (e) {
      return new Response('Error fetching stats', { status: 500 });
    }
  }

  // =========================================
  // GitHub API Proxy — restricted to Vapor repo
  // =========================================
  const githubUrl = `https://api.github.com${url.pathname}${url.search}`;

  // Build headers for GitHub request
  const githubHeaders = new Headers();
  githubHeaders.set('Authorization', `token ${GITHUB_PAT}`);
  githubHeaders.set('User-Agent', request.headers.get('User-Agent') || 'Vapor-Updater/1.0');
  githubHeaders.set('Accept', request.headers.get('Accept') || 'application/vnd.github.v3+json');

  if (request.method === 'POST') {
    githubHeaders.set('Content-Type', 'application/json');
  }

  try {
    // A moved repo answers 301/307 pointing at /repositories/<id>/... fetch()
    // follows that by itself for GET, but turns a POST into a GET on a 301, so
    // a bug report would read the issue list and create nothing. Writes follow
    // ONE redirect by hand with the same method and body, and only to
    // api.github.com, so the PAT never leaves GitHub's API host.
    const isWrite = ['POST', 'PUT', 'PATCH'].includes(request.method);
    const fetchOptions = {
      method: request.method,
      headers: githubHeaders,
      redirect: isWrite ? 'manual' : 'follow'
    };

    if (isWrite) {
      fetchOptions.body = await request.text();
    }

    let response = await fetch(githubUrl, fetchOptions);

    const location = response.headers.get('Location');
    if (isWrite && [301, 302, 307, 308].includes(response.status) && location) {
      const next = new URL(location, githubUrl);
      if (next.origin !== 'https://api.github.com') {
        return new Response('Unexpected redirect from GitHub', { status: 424 });
      }
      response = await fetch(next.toString(), fetchOptions);
    }

    const newResponse = new Response(response.body, response);
    newResponse.headers.set('Access-Control-Allow-Origin', '*');
    newResponse.headers.set('Access-Control-Allow-Methods', 'GET, HEAD, POST, OPTIONS');

    return newResponse;
  } catch (error) {
    return new Response(`Proxy error: ${error.message}`, { status: 500 });
  }
}