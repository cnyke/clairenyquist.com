/* SETI ridgeline: Breakthrough Listen's Voyager 1 observation, drawn as a
 * 96-stave score and played as one.
 *
 * The data is a single 18.25-second integration from the Green Bank Telescope,
 * X-band, 2016-09-19. 28,800 consecutive frequency channels of 2.79 Hz each are
 * cut into 96 rows of 300, so every vertex on every ridge is one native channel.
 * Nothing is binned, smoothed or interpolated.
 *
 * All 96 rows sound at once. Each row is a sine voice whose pitch is set by its
 * radio frequency, high row to high note, and one playhead sweeps left to right
 * across the whole plate, driving every voice's loudness from its own line. So
 * the wash you hear is 96 channels of thermal noise, and when the playhead
 * crosses Voyager's carrier one voice leaps out of it.
 *
 * The ridges are expensive to draw (about 29,000 vertices), so they are painted
 * once into an offscreen buffer and the moving parts are overlaid on top.
 */
(function () {
  "use strict";

  var DATA_URL = "/data/seti-voyager-ridgeline.json";

  // ---- logical drawing space, scaled to fit the container ----
  var W = 960,
    ML = 96,
    MR = 58,
    TOP = 40,
    BOT = 58,
    ROW_GAP = 9.2,
    PEAK = 62; // full-scale ridge height, about 6.7 row gaps

  var INK = "#1f2937", // gray-800, the ridge line
    PAPER = "#ffffff", // fill under each ridge, so ridges occlude
    ACCENT = "#2563eb", // blue-600, the site's link color
    MUTED = "#9ca3af",
    FAINT = "#e5e7eb";

  // ---- audio ----
  var SWEEP = 26, // seconds for one pass across the plate at 1x
    F_TOP = 1568, // G6, the top row's resting pitch
    OCTAVES = 3, // down to G3, 196 Hz, on the bottom row
    BEND = 1.4, // octaves a line bends its own voice at full scale
    SHARP = 1.8, // loudness curve; see buildGain
    VOICE = 0.9; // per-voice scale, set so the carrier peaks near -2 dBFS

  var meta = null,
    vals = null, // 0..1, lifted off the noise floor, for drawing and sound
    raw = null, // 0..1 straight from the file, for the dB readout
    ROWS = 0,
    COLS = 0,
    plotW = 0,
    H = 0,
    ready = false;

  // The three real signals, pinned to the channels they actually sit in rather
  // than found by a runtime heuristic, so the labels cannot drift off the data.
  // Each sideband is a modulated region roughly 700 Hz wide with its own
  // internal structure; the channel named here is that region's strongest.
  var peaks = [
    { ch: 739819, label: "upper sideband, +22.7 kHz" },
    { ch: 747929, label: "Voyager 1 carrier" },
    { ch: 755923, label: "lower sideband, −22.3 kHz" }
  ];

  var ctx = null,
    master = null,
    voices = null;
  var playing = false,
    startT = 0,
    startCol = 0,
    speed = 1,
    headCol = -1,
    hoverRow = -1,
    hoverCol = -1;

  function chanOf(r, c) {
    return meta.ch_start + r * COLS + c;
  }
  function mhzOf(r, c) {
    return meta.fch1 + meta.foff * chanOf(r, c);
  }
  function dbOf(r, c) {
    return meta.db_lo + raw[r * COLS + c] * (meta.db_hi - meta.db_lo);
  }

  // ---------------------------------------------------------------- audio
  function initAudio() {
    if (ctx) return;
    var AC = window.AudioContext || window.webkitAudioContext;
    ctx = new AC();

    // Only catches the carrier. Everything else runs well under the threshold,
    // so the wash is never pumped and the one loud event stays loud.
    var comp = ctx.createDynamicsCompressor();
    comp.threshold.value = -6;
    comp.ratio.value = 4;
    comp.knee.value = 8;
    comp.attack.value = 0.005;
    comp.release.value = 0.2;
    comp.connect(ctx.destination);

    master = ctx.createGain();
    master.gain.value = 1;
    master.connect(comp);

    // A plain generated hall, so 96 voices read as one room.
    var len = Math.floor(ctx.sampleRate * 2.1),
      imp = ctx.createBuffer(2, len, ctx.sampleRate);
    for (var ch = 0; ch < 2; ch++) {
      var d = imp.getChannelData(ch);
      for (var j = 0; j < len; j++)
        d[j] = (Math.random() * 2 - 1) * Math.pow(1 - j / len, 2.6);
    }
    var conv = ctx.createConvolver();
    conv.buffer = imp;
    var wet = ctx.createGain();
    wet.gain.value = 0.4;
    conv.connect(wet);
    wet.connect(comp);
    master.connect(conv);
  }

  // One row's line becomes one voice's loudness envelope across the sweep.
  //
  // The exponent needs care, and the arithmetic is not the obvious one. Ninety-
  // six sines at ninety-six different frequencies sum incoherently, so the wash
  // they make is the root of the sum of squares, not the sum: ninety-five noise
  // voices come out only about ten times one of them, not ninety-five times.
  // That already flatters the carrier, so the exponent does not have to, and an
  // aggressive one just buries the noise floor below hearing. At 1.8 the carrier
  // still stands about seven times the wash in RMS, roughly 17 dB, which reads
  // as unmistakable without the other ninety-five voices going silent to buy it.
  // It changes contrast, not order: the mapping stays monotonic, so nothing is
  // ever louder than something the plate draws higher.
  function buildGain(r, fromCol) {
    var n = COLS - fromCol,
      out = new Float32Array(n),
      base = r * COLS;
    for (var i = 0; i < n; i++)
      out[i] = Math.pow(vals[base + fromCol + i], SHARP) * VOICE;
    return out;
  }

  // Pitch follows the line as well as loudness. Each row rests at a pitch set
  // by its radio frequency, high row to high note, and its own line bends it
  // from there: up to BEND octaves at full scale. Thermal noise is a fine
  // shimmer of a few percent, so a row still sits at its own pitch, and the
  // carrier throws its voice nearly an octave and a half above where it began.
  function buildPitch(r, fromCol) {
    var n = COLS - fromCol,
      out = new Float32Array(n),
      base = r * COLS,
      rest = F_TOP * Math.pow(2, -OCTAVES * (r / (ROWS - 1)));
    for (var i = 0; i < n; i++)
      out[i] = rest * Math.pow(2, BEND * vals[base + fromCol + i]);
    return out;
  }

  function startVoices(fromCol, when, dur) {
    voices = [];
    for (var r = 0; r < ROWS; r++) {
      var osc = ctx.createOscillator();
      osc.type = "sine";
      osc.frequency.setValueCurveAtTime(buildPitch(r, fromCol), when, dur);
      var g = ctx.createGain();
      g.gain.value = 0;
      g.gain.setValueCurveAtTime(buildGain(r, fromCol), when, dur);
      osc.connect(g);
      g.connect(master);
      osc.start(when);
      osc.stop(when + dur + 0.05);
      voices.push(osc);
    }
    // Every oscillator starts at phase zero, which would click; ease in. The
    // matching fade at the far end keeps the loop from clicking when the sweep
    // restarts, so the two passes are joined by a short breath rather than a cut.
    master.gain.cancelScheduledValues(when);
    master.gain.setValueAtTime(0, when);
    master.gain.linearRampToValueAtTime(1, when + 0.04);
    master.gain.setValueAtTime(1, when + dur - 0.06);
    master.gain.linearRampToValueAtTime(0, when + dur);
  }

  function stopVoices() {
    if (!voices) return;
    for (var i = 0; i < voices.length; i++) {
      try {
        voices[i].stop();
      } catch (e) {}
    }
    voices = null;
  }

  // ---------------------------------------------------------------- sketch
  var sketch = function (p) {
    var base = null,
      scaleF = 1;

    function rowY(r) {
      return TOP + r * ROW_GAP;
    }
    function colX(c) {
      return ML + (c / (COLS - 1)) * plotW;
    }

    function paintBase() {
      base = p.createGraphics(W, H);
      base.pixelDensity(Math.min(2, window.devicePixelRatio || 1));
      var g = base;
      g.background(PAPER);

      // frequency gutter, every 12 rows
      g.textFont("ui-monospace, SFMono-Regular, Menlo, monospace");
      g.textSize(9);
      g.textAlign(g.RIGHT, g.CENTER);
      for (var t = 0; t < ROWS; t += 12) {
        g.noStroke();
        g.fill(MUTED);
        g.text(mhzOf(t, 0).toFixed(4), ML - 12, rowY(t));
        g.stroke(FAINT);
        g.line(ML - 8, rowY(t), ML - 4, rowY(t));
      }

      // the ridges, back to front, so a tall peak covers the staves above it
      g.strokeWeight(1);
      g.strokeJoin(g.ROUND);
      g.stroke(INK);
      g.fill(PAPER);
      for (var r = 0; r < ROWS; r++) {
        var y0 = rowY(r);
        g.beginShape();
        g.vertex(ML, y0 + 1);
        for (var c = 0; c < COLS; c++)
          g.vertex(colX(c), y0 - vals[r * COLS + c] * PEAK);
        g.vertex(ML + plotW, y0 + 1);
        g.endShape();
      }

      // direct labels on the three real signals
      g.textFont("Lexend, ui-sans-serif, system-ui, sans-serif");
      g.textSize(10);
      for (var q = 0; q < peaks.length; q++) {
        var pk = peaks[q],
          px = colX(pk.c),
          py = rowY(pk.r) - vals[pk.i] * PEAK,
          right = pk.c < COLS * 0.62,
          lx = right ? px + 10 : px - 10;
        g.stroke(ACCENT);
        g.strokeWeight(1);
        g.line(px, py - 3, lx, py - 10);
        // a paper pill behind the label, or the noise runs straight through it
        var tw = g.textWidth(pk.label),
          tx = lx + (right ? 2 : -2 - tw);
        g.noStroke();
        g.fill(PAPER);
        g.rect(tx - 4, py - 21, tw + 8, 14, 2);
        g.fill(ACCENT);
        g.textAlign(g.LEFT, g.BOTTOM);
        g.text(pk.label, tx, py - 9);
      }

      // footer scale
      g.noStroke();
      g.fill(MUTED);
      g.textSize(10);
      g.textAlign(g.LEFT, g.TOP);
      g.text(
        "each row spans 838 Hz, left to right · rows run top to bottom, descending in frequency",
        ML,
        TOP + ROWS * ROW_GAP + 18
      );
      g.textAlign(g.RIGHT, g.TOP);
      g.text("2.79 Hz per vertex", W - MR, TOP + ROWS * ROW_GAP + 18);
    }

    function layout() {
      var host = document.getElementById("seti-canvas"),
        w = Math.max(300, host.clientWidth);
      scaleF = Math.min(1, w / W);
      p.resizeCanvas(W * scaleF, H * scaleF);
    }

    p.setup = function () {
      var host = document.getElementById("seti-canvas");
      var cnv = p.createCanvas(host.clientWidth, 300);
      cnv.parent(host);
      p.pixelDensity(Math.min(2, window.devicePixelRatio || 1));
      p.noLoop();

      cnv.elt.addEventListener("mouseleave", function () {
        hoverRow = -1;
        p.redraw();
      });

      fetch(DATA_URL)
        .then(function (r) {
          return r.json();
        })
        .then(function (j) {
          meta = j.meta;
          ROWS = meta.rows;
          COLS = meta.cols;
          plotW = W - ML - MR;
          H = TOP + ROWS * ROW_GAP + BOT;

          var bin = atob(j.b64);
          raw = new Float32Array(bin.length);
          for (var i = 0; i < bin.length; i++) raw[i] = bin.charCodeAt(i) / 255;

          // lift the noise floor off the baseline so the texture in every row
          // stays legible instead of every ridge burying the one above it
          var sorted = Float32Array.from(raw).sort(),
            floor = sorted[Math.floor(sorted.length * 0.02)];
          vals = new Float32Array(raw.length);
          for (var k = 0; k < raw.length; k++)
            vals[k] = Math.max(0, (raw[k] - floor) / (1 - floor));

          // resolve each labelled channel to its cell in the grid
          for (var q = 0; q < peaks.length; q++) {
            var i2 = peaks[q].ch - meta.ch_start;
            peaks[q].i = i2;
            peaks[q].r = Math.floor(i2 / COLS);
            peaks[q].c = i2 % COLS;
          }

          ready = true;
          paintBase();
          layout();
          p.redraw();
          document.getElementById("seti-play").disabled = false;
          document.getElementById("seti-loading").style.display = "none";
        });

      window.addEventListener("resize", function () {
        if (ready) {
          layout();
          p.redraw();
        }
      });
    };

    p.draw = function () {
      if (!ready) return;
      p.clear();
      p.image(base, 0, 0, W * scaleF, H * scaleF);
      p.push();
      p.scale(scaleF);

      if (playing) {
        var perCol = SWEEP / speed / (COLS - 1);
        headCol = startCol + (ctx.currentTime - startT) / perCol;
        if (headCol >= COLS - 1) {
          // ran off the right edge: sweep again from the left. Clearing
          // `playing` first stops this branch firing on every frame until the
          // new pass has actually been scheduled.
          headCol = COLS - 1;
          playing = false;
          start(0);
        }
      }

      // the playhead: one vertical line, every row sounding at once
      if (playing && headCol >= 0) {
        var hxp = colX(headCol);
        p.stroke(ACCENT);
        p.strokeWeight(1.2);
        p.line(hxp, TOP - PEAK * 0.35, hxp, TOP + (ROWS - 1) * ROW_GAP + 4);
        // mark where the playhead crosses each of the three real signals
        p.noStroke();
        for (var q2 = 0; q2 < peaks.length; q2++) {
          var pk2 = peaks[q2];
          if (Math.abs(headCol - pk2.c) < 2.5) {
            p.fill(ACCENT);
            p.circle(colX(pk2.c), rowY(pk2.r) - vals[pk2.i] * PEAK, 7);
          }
        }
      }

      // hover readout
      if (hoverRow >= 0) {
        var hx = colX(hoverCol),
          hy = rowY(hoverRow) - vals[hoverRow * COLS + hoverCol] * PEAK;
        p.stroke(ACCENT);
        p.strokeWeight(1);
        p.line(hx, rowY(hoverRow) + 1, hx, hy);
        p.noStroke();
        p.fill(ACCENT);
        p.circle(hx, hy, 4.5);

        var d = dbOf(hoverRow, hoverCol),
          txt =
            mhzOf(hoverRow, hoverCol).toFixed(6) +
            " MHz   " +
            (d >= 0 ? "+" : "") +
            d.toFixed(2) +
            " dB",
          sub = "channel " + chanOf(hoverRow, hoverCol).toLocaleString();
        p.textFont("ui-monospace, SFMono-Regular, Menlo, monospace");
        p.textSize(10);
        p.textAlign(p.LEFT, p.TOP);
        var bw = Math.max(p.textWidth(txt), p.textWidth(sub)) + 16,
          bx = Math.min(Math.max(hx - bw / 2, ML), W - MR - bw),
          by = Math.max(hy - 46, 2);
        p.fill(255, 250);
        p.stroke(FAINT);
        p.strokeWeight(1);
        p.rect(bx, by, bw, 32, 3);
        p.noStroke();
        p.fill(INK);
        p.text(txt, bx + 8, by + 6);
        p.fill(MUTED);
        p.text(sub, bx + 8, by + 18);
      }
      p.pop();
    };

    function pick() {
      if (!ready) return null;
      var mx = p.mouseX / scaleF,
        my = p.mouseY / scaleF;
      if (mx < ML || mx > ML + plotW) return null;
      var r = Math.round((my - TOP) / ROW_GAP),
        c = Math.round(((mx - ML) / plotW) * (COLS - 1));
      if (r < 0 || r >= ROWS || c < 0 || c >= COLS) return null;
      return { r: r, c: c };
    }

    p.mouseMoved = function () {
      var h = pick();
      hoverRow = h ? h.r : -1;
      hoverCol = h ? h.c : -1;
      if (!playing) p.redraw();
    };
    // click anywhere on the plate to start the sweep from that column
    p.mousePressed = function () {
      var h = pick();
      if (!h) return;
      stop();
      start(h.c);
    };

    p.setPlaying = function (on) {
      if (on) p.loop();
      else {
        p.noLoop();
        p.redraw();
      }
    };
    window.__setiP5 = p;
  };

  // ---------------------------------------------------------------- controls
  // Chrome hands back a suspended context whose clock reads 0 and stays there
  // until resume() actually settles, which took nearly two seconds in testing.
  // Scheduling against that frozen clock left the playhead parked at the start
  // looking broken, so wait for the resume before touching currentTime. `gen`
  // discards a resume that lands after the user has already pressed stop.
  var gen = 0;
  function start(fromCol) {
    initAudio();
    stopVoices();
    startCol = Math.max(0, Math.min(COLS - 2, fromCol || 0));
    var mine = ++gen;
    document.getElementById("seti-play").textContent = "Pause";
    ctx.resume().then(function () {
      if (mine !== gen) return;
      var dur = ((COLS - 1 - startCol) / (COLS - 1)) * (SWEEP / speed),
        when = ctx.currentTime + 0.06;
      startVoices(startCol, when, dur);
      startT = when;
      headCol = startCol;
      playing = true;
      window.__setiP5.setPlaying(true);
    });
  }
  function stop() {
    gen++;
    stopVoices();
    playing = false;
    document.getElementById("seti-play").textContent = "Play ▶";
    if (window.__setiP5) window.__setiP5.setPlaying(false);
  }

  window.addEventListener("DOMContentLoaded", function () {
    new p5(sketch);

    document.getElementById("seti-play").addEventListener("click", function () {
      if (playing) {
        headCol = Math.round(headCol);
        stop();
      } else start(headCol >= COLS - 2 || headCol < 0 ? 0 : headCol);
    });
    document
      .getElementById("seti-restart")
      .addEventListener("click", function () {
        stop();
        start(0);
      });
    Array.prototype.forEach.call(
      document.querySelectorAll(".seti-sp"),
      function (b) {
        b.addEventListener("click", function () {
          var was = playing,
            at = Math.round(headCol);
          Array.prototype.forEach.call(
            document.querySelectorAll(".seti-sp"),
            function (o) {
              o.removeAttribute("data-active");
            }
          );
          b.setAttribute("data-active", "true");
          speed = parseFloat(b.dataset.speed);
          stop();
          if (was) start(at < 0 ? 0 : at);
        });
      }
    );
  });
})();
