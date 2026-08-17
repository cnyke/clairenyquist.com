/*
 * "A Year in Your Data" — example viz.
 * Source: one person's YouTube Music library (Google Takeout).
 * Artists A→Z, one bar each. Bar length + color = number of songs
 * (red = most, violet = fewest).
 *
 * Sound maps to the DATA. The rhythm is steady — one beat per artist as the
 * alphabet scrolls by. The PITCH is set by how many songs that artist has,
 * exactly like the color: more songs → higher pitch. A run of one-song
 * artists keeps ticking at the same low pitch; the pitch jumps when an
 * artist has more songs.
 *
 * GRABBER: drag the list (or the handle on the right) to move the play
 * position anywhere in the A→Z song list — the viz and the sound follow,
 * scrubbing as you go.
 */
(function () {
  // Data is fetched once, before any p5 instance is created (see loadData /
  // ensureSketch below). Relying on p5's preload() to populate it raced with
  // setup() and intermittently left it undefined, so we load it ourselves.
  let DATA = null;

  const sketch = (p) => {
    let artists, MAXN, MINN, TOTAL;

    // layout
    const headerH = 64;
    const rowH = 20;
    const gutter = 168;
    const padRight = 64;     // room for count label + scrollbar
    const playheadY = headerH + 34;
    let H = 600;

    // scrollbar / grabber geometry (recomputed in draw)
    const sbW = 10;
    let sbX = 0, sbTop = 0, sbBot = 0, sbH = 0, thumbY = 0, thumbH = 28;

    // playback (one beat per artist)
    let playing = false;
    let finished = false;
    let curArtist = 0;
    let acc = 0;           // ms accumulator for the beat clock
    let beatsPerSec = 6;   // 1× — the rhythm
    let beatFlash = 0;
    let scrollY = 0;
    let audioReady = false;
    let synth;

    // dragging state
    let dragMode = null;   // 'content' | 'thumb' | null
    let thumbGrab = 0;     // offset within thumb when grabbed
    let scrubQueue = [];   // artists the grabber has passed, waiting to sound
    let scrubAcc = 0;      // ms accumulator for draining the scrub run
    let scrubVoice = 0;    // index currently sounding from the scrub run
    const SCRUB_RATE = 45; // notes/sec played while scrubbing through
    const SCRUB_CAP = 220; // bound the run on very fast drags

    // pitch maps to song count, quantized to a pleasant scale.
    // Low pitch = fewest songs (violet), high pitch = most songs (red).
    const SCALE_MIDI = [
      48, 50, 52, 55, 57, 60, 62, 64, 67, 69, 72, 74, 76, 79, 81, 84,
    ]; // C major pentatonic, C3 → C6

    p.setup = function () {
      if (!DATA || !DATA.artists) return;   // data must be loaded first
      const holder = document.getElementById("yiyd-canvas");
      const w = holder.clientWidth || 880;
      const cnv = p.createCanvas(w, H);
      cnv.parent(holder);
      p.colorMode(p.HSB, 360, 100, 100, 1);
      p.textFont("Helvetica");

      artists = DATA.artists;
      MAXN = DATA.max;
      MINN = DATA.min;
      TOTAL = DATA.total;

      computeBars(w);
      wireControls();
      p.noLoop();
      p.redraw();
      p._yiydReady = true;   // setup finished, canvas is live
    };

    function computeBars(w) {
      const barMax = w - gutter - padRight;
      const sMin = Math.sqrt(MINN), sMax = Math.sqrt(MAXN);
      for (const a of artists) {
        const t = (Math.sqrt(a.n) - sMin) / (sMax - sMin || 1); // 0 fewest → 1 most
        a.hue = 280 * (1 - t);                                  // violet → red
        a.len = Math.max(2, (a.n / MAXN) * barMax);
        const idx = Math.round(t * (SCALE_MIDI.length - 1));
        a.freq = p.midiToFreq(SCALE_MIDI[idx]);                 // pitch ← count
      }
    }

    p.windowResized = function () {
      const holder = document.getElementById("yiyd-canvas");
      const w = holder.clientWidth || 880;
      p.resizeCanvas(w, H);
      computeBars(w);
      if (!playing) { p.loop(); }
    };

    function playArtist(i) {
      const a = artists[i];
      if (a && audioReady && synth) synth.play(a.freq, 0.5, 0, 0.12);
    }

    function beat() {
      playArtist(curArtist);
      beatFlash = 1;
      curArtist++;
      if (curArtist >= TOTAL) {
        playing = false;
        finished = true;
        setBtn("Replay ↺");
      }
    }

    const scrollMax = () => Math.max(0, headerH + TOTAL * rowH - (H - 40));
    const artistAtPlayhead = (sy) =>
      p.constrain(Math.round((sy + playheadY - headerH - rowH / 2) / rowH), 0, TOTAL - 1);

    p.draw = function () {
      const scrubbing = dragMode !== null;
      const dt = Math.min(p.deltaTime, 100); // ignore the spike after a hidden tab

      if (playing && !finished && !scrubbing) {
        acc += dt;
        const interval = 1000 / beatsPerSec;
        let guard = 0;
        while (acc >= interval && playing && guard < 64) {
          acc -= interval;
          beat();
          guard++;
        }
      }
      beatFlash *= 0.82;

      // drain the scrub run — sound every artist the grabber passed over
      if (scrubQueue.length) {
        scrubAcc += dt;
        const iv = 1000 / SCRUB_RATE;
        let g = 0;
        while (scrubAcc >= iv && scrubQueue.length && g < 32) {
          scrubAcc -= iv;
          scrubVoice = scrubQueue.shift();
          playArtist(scrubVoice);
          beatFlash = 1;
          g++;
        }
        if (!playing) p.loop();
      }

      // scroll: direct while scrubbing, else ease toward current artist
      const idx = Math.min(curArtist, TOTAL - 1);
      const target = p.constrain(headerH + idx * rowH + rowH / 2 - playheadY, 0, scrollMax());
      if (!scrubbing) scrollY += (target - scrollY) * 0.18;

      p.background(0, 0, 99);

      // bars in view
      const firstVisible = Math.max(0, Math.floor((scrollY - headerH) / rowH) - 1);
      const lastVisible = Math.min(TOTAL - 1, Math.ceil((scrollY + H - headerH) / rowH));
      p.textAlign(p.LEFT, p.CENTER);
      for (let i = firstVisible; i <= lastVisible; i++) {
        const a = artists[i];
        const y = headerH + i * rowH - scrollY;
        const cy = y + rowH / 2;
        const isCur = i === idx;
        const done = !scrubbing && playing && i < curArtist;
        const alpha = done ? 0.4 : isCur ? 1 : 0.85;

        if (isCur) {
          p.noStroke();
          p.fill(a.hue, 60, 96, 0.25 + 0.4 * beatFlash);
          p.rect(0, y, p.width, rowH);
        }

        p.noStroke();
        p.fill(a.hue, 80, isCur ? 96 : done ? 78 : 90, alpha);
        p.rect(gutter, y + 2, a.len, rowH - 4, 2);

        p.fill(0, 0, done ? 55 : 18, alpha);
        p.textSize(11);
        let nm = a.name;
        if (nm.length > 26) nm = nm.slice(0, 25) + "…";
        p.text(nm, 10, cy);

        p.fill(a.hue, 70, 50, alpha);
        p.textSize(10);
        p.text(a.n, gutter + a.len + 6, cy);
      }

      // header band
      p.noStroke();
      p.fill(0, 0, 99);
      p.rect(0, 0, p.width, headerH);
      p.fill(0, 0, 18);
      p.textAlign(p.LEFT, p.BASELINE);
      p.textSize(13);
      p.text("YouTube Music library · 1,473 artists A→Z · pitch = songs per artist", 10, 22);
      p.fill(0, 0, 45);
      p.textSize(10);
      const a0 = artists[idx];
      p.text(
        a0 ? `now: ${a0.name} — ${a0.n} song${a0.n === 1 ? "" : "s"}   ·   drag to scrub` : "done",
        10, 40
      );

      // current letter + progress
      const letter = (a0?.name || "A").charAt(0).toUpperCase();
      p.textAlign(p.RIGHT, p.BASELINE);
      p.textSize(34);
      p.fill(p.map(idx, 0, TOTAL, 280, 0), 80, 80);
      p.text(/[A-Z]/.test(letter) ? letter : "#", p.width - 18, 34);
      p.textSize(10);
      p.fill(0, 0, 50);
      p.text(Math.round((idx / (TOTAL - 1)) * 100) + "%", p.width - 18, 50);

      // playhead line + "plays here" marker
      p.stroke(0, 0, 35, 0.55);
      p.strokeWeight(1);
      p.line(0, playheadY, p.width - sbW - 8, playheadY);
      p.noStroke();
      p.fill(0, 0, 35);
      p.triangle(0, playheadY - 6, 0, playheadY + 6, 10, playheadY);

      drawScrollbar();

      // settle to a stop when idle
      if (!playing && !scrubbing && scrubQueue.length === 0 && Math.abs(target - scrollY) < 0.4)
        p.noLoop();
    };

    function drawScrollbar() {
      sbX = p.width - sbW - 4;
      sbTop = headerH + 6;
      sbBot = H - 8;
      sbH = sbBot - sbTop;
      const contentH = TOTAL * rowH;
      thumbH = Math.max(30, sbH * ((H - headerH) / contentH));
      const frac = scrollMax() > 0 ? scrollY / scrollMax() : 0;
      thumbY = sbTop + frac * (sbH - thumbH);

      // track
      p.noStroke();
      p.fill(0, 0, 90);
      p.rect(sbX, sbTop, sbW, sbH, sbW / 2);
      // thumb (the grabber)
      const hot = dragMode === "thumb" || overThumb(p.mouseX, p.mouseY);
      p.fill(0, 0, hot ? 45 : 62);
      p.rect(sbX, thumbY, sbW, thumbH, sbW / 2);
      // grip dots
      p.fill(0, 0, 99);
      const gx = sbX + sbW / 2, gy = thumbY + thumbH / 2;
      for (let d = -1; d <= 1; d++) p.circle(gx, gy + d * 4, 2);
    }

    // ---- interaction ----
    const inCanvas = (x, y) => x >= 0 && x <= p.width && y >= 0 && y <= H;
    const overThumb = (x, y) =>
      x >= sbX - 4 && x <= sbX + sbW + 4 && y >= thumbY - 2 && y <= thumbY + thumbH + 2;
    const overTrack = (x, y) =>
      x >= sbX - 4 && x <= sbX + sbW + 4 && y >= sbTop && y <= sbBot;

    function scrubToScroll(sy) {
      scrollY = p.constrain(sy, 0, scrollMax());
      const a = artistAtPlayhead(scrollY);
      if (a < TOTAL) finished = false;
      if (a !== curArtist) {                 // queue every artist we passed
        const step = a > curArtist ? 1 : -1;
        for (let i = curArtist + step; ; i += step) {
          scrubQueue.push(i);
          if (i === a) break;
        }
        if (scrubQueue.length > SCRUB_CAP) scrubQueue.splice(0, scrubQueue.length - SCRUB_CAP);
      }
      curArtist = a;
    }

    p.mousePressed = function () {
      if (!inCanvas(p.mouseX, p.mouseY)) return;
      if (overThumb(p.mouseX, p.mouseY)) {
        dragMode = "thumb";
        thumbGrab = p.mouseY - thumbY;
      } else if (overTrack(p.mouseX, p.mouseY)) {
        dragMode = "thumb";
        thumbGrab = thumbH / 2;                 // jump thumb to cursor
        thumbFromMouse();
      } else {
        dragMode = "content";
      }
      scrubAcc = 0;
      p.loop();
      return false;
    };

    function thumbFromMouse() {
      const t = p.constrain((p.mouseY - thumbGrab - sbTop) / (sbH - thumbH), 0, 1);
      scrubToScroll(t * scrollMax());
    }

    p.mouseDragged = function () {
      if (dragMode === "thumb") {
        thumbFromMouse();
        return false;
      } else if (dragMode === "content") {
        scrubToScroll(scrollY + (p.pmouseY - p.mouseY)); // grab & move the list
        return false;
      }
    };

    p.mouseReleased = function () {
      if (dragMode) {
        dragMode = null;
        acc = 0;                  // resume rhythm cleanly from new position
        if (!playing) p.loop();   // let scroll settle / redraw once
      }
    };

    p.mouseMoved = function () {
      if (!inCanvas(p.mouseX, p.mouseY)) { p.cursor(p.ARROW); return; }
      p.cursor(dragMode ? "grabbing" : "grab");
    };

    // ---- controls ----
    let playBtn;
    function setBtn(label) { if (playBtn) playBtn.textContent = label; }

    async function ensureAudio() {
      if (audioReady) return;
      await p.userStartAudio();
      synth = new p5.MonoSynth();
      synth.setADSR(0.004, 0.06, 0.2, 0.12);
      audioReady = true;
    }

    function start() {
      if (finished) reset();
      playing = true;
      acc = 0;
      p.loop();
      setBtn("Pause ⏸");
    }
    function pause() { playing = false; setBtn("Play ▶"); p.loop(); }
    function reset() { curArtist = 0; acc = 0; finished = false; }

    function wireControls() {
      // onclick (not addEventListener) so re-wiring never stacks handlers
      playBtn = document.getElementById("yiyd-play");
      playBtn.onclick = async () => {
        await ensureAudio();
        if (playing) pause(); else start();
      };
      document.getElementById("yiyd-restart").onclick = () => {
        reset(); setBtn("Play ▶"); p.loop();
      };
      const speeds = { "yiyd-sp-1": 6, "yiyd-sp-2": 12, "yiyd-sp-3": 24 };
      Object.keys(speeds).forEach((id) => {
        document.getElementById(id).onclick = (e) => {
          beatsPerSec = speeds[id];
          document.querySelectorAll(".yiyd-sp").forEach((b) => b.removeAttribute("data-active"));
          e.currentTarget.setAttribute("data-active", "true");
        };
      });
    }

    // repaint after returning to the page (tab unhide / bfcache restore)
    p._yiydRepaint = function () {
      acc = 0; scrubAcc = 0;
      p.loop();
    };
  };

  // ---- robust lifecycle: survive tab-switches, bfcache, and re-navigation ----
  let instance = null;
  let building = false;
  let dataPromise = null;

  const holder = () => document.getElementById("yiyd-canvas");
  const hasCanvas = () => {
    const h = holder();
    return h && h.querySelector("canvas");
  };

  // fetch the dataset exactly once; reused across rebuilds
  function loadData() {
    if (!dataPromise) {
      dataPromise = fetch("/music-library-artists.json")
        .then((r) => {
          if (!r.ok) throw new Error("HTTP " + r.status);
          return r.json();
        })
        .catch((e) => { dataPromise = null; throw e; }); // allow retry
    }
    return dataPromise;
  }

  async function ensureSketch() {
    const h = holder();
    if (!h) return;                              // not on this page
    if (!window.p5) { setTimeout(ensureSketch, 60); return; }

    if (instance) {
      // still initializing (setup in flight) — leave it alone
      if (!instance._yiydReady) return;
      if (hasCanvas()) {                         // alive — just repaint
        if (instance._yiydRepaint) instance._yiydRepaint();
        return;
      }
      // was ready but lost its canvas (bfcache / cleared) → rebuild cleanly
      try { instance.remove(); } catch (e) {}
      instance = null;
      h.innerHTML = "";
    }

    if (building) return;                        // a build is already in flight
    building = true;
    try {
      if (!DATA) DATA = await loadData();        // data ready before p5 starts
    } catch (e) {
      building = false;
      setTimeout(ensureSketch, 300);             // network hiccup — retry
      return;
    }
    // guard against state changing during the await
    if (!holder() || instance) { building = false; return; }
    try { instance = new p5(sketch); } catch (e) { setTimeout(ensureSketch, 120); }
    building = false;
  }

  // (re)initialize on every way a user can arrive at / return to the page
  ["DOMContentLoaded", "load", "pageshow", "astro:page-load"].forEach((ev) =>
    window.addEventListener(ev, ensureSketch)
  );
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) ensureSketch();
  });
  // tear down before leaving so we don't leak an audio/animation loop
  window.addEventListener("pagehide", () => {
    if (instance) { try { instance.remove(); } catch (e) {} instance = null; }
  });

  if (document.readyState !== "loading") ensureSketch();
})();
