/* ==========================================================================
   betweenness.js — counting the journeys that pass through a town.

   A scene array for the shared kit (assets/anim.css + assets/anim.js); it
   carries no sequencer and no copy of the kit's stylesheet. See the header of
   assets/anim.js for the contract.

   Nine towns, nine lines and one loop in the south, so the picture reads as a
   network rather than a stick. The loop earns its place: A to H really does go
   round the bottom, which is the one route on the board a viewer would not
   have guessed. What the shape is NOT is a machine built to also prove the
   page's other point — that a two-line town can outscore a ten-line one. Bend a
   topology to argue a second thing and it stops being a clean example of the
   first, and the counting is all this stage is for.

   Every pair has exactly one shortest route (checked, weighted by the distances
   drawn), so no scene has to explain ties. The 36 pairs and their middles are
   written out below rather than searched at page load.

   Drawn with a pen, not a plotter: each line is bowed and gone over twice, and
   each town is a slightly out-of-round circle. Seeded, so replaying does not
   redraw the network somewhere else.
   ========================================================================== */

(window.animReady = window.animReady || []).push(function () {

  /* ---------------------------------------------------------------- data --- */
  const NAME = ["A", "B", "C", "D", "E", "F", "G", "H", "I"];
  const POS = [[60, 200], [155, 128], [262, 196], [368, 124], [478, 196],
               [262, 62], [155, 285], [368, 285], [560, 120]];
  const EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [2, 5],
                 [1, 6], [3, 7], [4, 8], [6, 7]];
  const R = 21;

  /* Each town's running total, placed clear of every line into it. */
  const BADGE = [[60, 246], [128, 100], [262, 244], [396, 96], [478, 244],
                 [262, 30], [155, 332], [368, 332], [560, 88]];

  const PAIRS = [
    [0, 1, []], [0, 2, [1]], [0, 3, [1, 2]], [0, 4, [1, 2, 3]],
    [0, 5, [1, 2]], [0, 6, [1]], [0, 7, [1, 6]], [0, 8, [1, 2, 3, 4]],
    [1, 2, []], [1, 3, [2]], [1, 4, [2, 3]], [1, 5, [2]],
    [1, 6, []], [1, 7, [6]], [1, 8, [2, 3, 4]], [2, 3, []],
    [2, 4, [3]], [2, 5, []], [2, 6, [1]], [2, 7, [3]],
    [2, 8, [3, 4]], [3, 4, []], [3, 5, [2]], [3, 6, [7]],
    [3, 7, []], [3, 8, [4]], [4, 5, [3, 2]], [4, 6, [3, 7]],
    [4, 7, [3]], [4, 8, []], [5, 6, [2, 1]], [5, 7, [2, 3]],
    [5, 8, [2, 3, 4]], [6, 7, []], [6, 8, [7, 3, 4]], [7, 8, [3, 4]]
  ];
  const FINAL = [0, 9, 13, 14, 7, 0, 2, 3, 0];
  const WINNER = 3;      /* D, on 14 of the 36 */

  const LONGEST = 7;     /* A to I, four towns in the middle */
  const ROUND_THE_BOTTOM = 6;  /* A to H, the route that goes the other way */

  /* --------------------------------------------------------------- scenes */
  const scenes = [
    {
      label: "Nine towns and the lines between them",
      note: "Betweenness asks one question of each town: how often does it sit in the middle of somebody else's journey?",
      async run(ctx) {
        ctx.build();
        await ctx.sleep(3200);
      }
    },
    {
      label: "Take one pair",
      note: "A to I runs through B, C, D and E. Each of the four picks up a point. A and I get nothing — the journey is theirs, they are not in the middle of it.",
      async run(ctx) {
        ctx.build();
        await ctx.sleep(1100);
        await ctx.route(LONGEST, false, 1500);
        await ctx.sleep(4200);
      }
    },
    {
      label: "The route is not always the obvious one",
      note: "A to H goes round the bottom, through B and G. Shorter that way — so G and H score, and C and D do not.",
      async run(ctx) {
        ctx.build();
        await ctx.route(LONGEST, true);
        await ctx.sleep(900);
        await ctx.route(ROUND_THE_BOTTOM, false, 1400);
        await ctx.sleep(4200);
      }
    },
    {
      label: "Now every pair",
      note: "Thirty-six pairs of towns, thirty-six routes. Every town in the middle of one picks up a point.",
      async run(ctx) {
        ctx.build();
        for (let i = 0; i < PAIRS.length; i++) {
          if (i === LONGEST || i === ROUND_THE_BOTTOM) continue;
          await ctx.route(i, false, 330);
        }
        await ctx.route(LONGEST, false, 330);
        await ctx.route(ROUND_THE_BOTTOM, false, 330);
        await ctx.sleep(4000);
      }
    },
    {
      label: "That is the score",
      note: "D sits on 14 of the 36 routes, C on 13, B on 9. The three towns at the ends are on none. Divide by the number of pairs and you have betweenness centrality.",
      async run(ctx) {
        ctx.build(true);
        await ctx.sleep(1200);
        ctx.crown();
        await ctx.sleep(5200);
      }
    }
  ];

  mountScenes(document.getElementById("bc-anim"), scenes, {
    stepsLabel: "Betweenness steps",

    helpers(ctx) {
      const box = ctx.$("[data-anim-clear]");
      const S = { tally: [], nodes: [], badges: [], geo: {}, done: 0 };

      /* Seeded, so the same network is drawn every time it is replayed. */
      function prng(seed) {
        let t = seed >>> 0;
        return function () {
          t += 0x6D2B79F5;
          let r = Math.imul(t ^ (t >>> 15), 1 | t);
          r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
          return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
        };
      }

      /* One bowed stroke between two towns. The control point is kept so the
         trail can be laid along the very same curve — draw the route straight
         over a bowed line and it floats off it. */
      function bow(p, q, seed, amp) {
        const rand = prng(seed);
        const dx = q[0] - p[0], dy = q[1] - p[1];
        const L = Math.hypot(dx, dy) || 1;
        const k = (rand() - 0.5) * 2 * (amp == null ? 7 : amp);
        return [(p[0] + q[0]) / 2 - (dy / L) * k, (p[1] + q[1]) / 2 + (dx / L) * k];
      }

      function qpath(p, c, q) {
        return "M" + p[0].toFixed(1) + " " + p[1].toFixed(1) +
               "Q" + c[0].toFixed(1) + " " + c[1].toFixed(1) +
               " " + q[0].toFixed(1) + " " + q[1].toFixed(1);
      }

      /* A town: a circle that missed. Fourteen samples with the radius nudged,
         joined through their midpoints so the result is smooth, not spiky. */
      function blob(cx, cy, r, seed) {
        const rand = prng(seed), N = 14, pts = [];
        for (let i = 0; i < N; i++) {
          const a = (i / N) * Math.PI * 2;
          const rr = r * (1 + (rand() - 0.5) * 0.17);
          pts.push([cx + Math.cos(a) * rr, cy + Math.sin(a) * rr]);
        }
        const mid = function (i, j) {
          return [(pts[i][0] + pts[j][0]) / 2, (pts[i][1] + pts[j][1]) / 2];
        };
        let m = mid(N - 1, 0);
        let d = "M" + m[0].toFixed(1) + " " + m[1].toFixed(1);
        for (let i = 0; i < N; i++) {
          const nxt = mid(i, (i + 1) % N);
          d += "Q" + pts[i][0].toFixed(1) + " " + pts[i][1].toFixed(1) +
               " " + nxt[0].toFixed(1) + " " + nxt[1].toFixed(1);
        }
        return d + "Z";
      }

      const key = function (u, v) { return u < v ? u + "-" + v : v + "-" + u; };

      function build(final) {
        box.textContent = "";
        S.tally = final ? FINAL.slice() : NAME.map(function () { return 0; });
        S.nodes = [];
        S.badges = [];
        S.geo = {};
        S.done = final ? PAIRS.length : 0;

        const svg = ctx.svgRoot("0 0 620 350", "bc-svg");

        EDGES.forEach(function (e, i) {
          const p = POS[e[0]], q = POS[e[1]];
          const c = bow(p, q, 7 * i + 3);
          S.geo[key(e[0], e[1])] = { p: p, c: c, q: q };
          svg.appendChild(ctx.svgEl("path", { "class": "anim-edge", d: qpath(p, c, q) }));
          /* The going-over stroke, out of register on purpose. */
          svg.appendChild(ctx.svgEl("path", {
            "class": "anim-edge bc-edge2",
            d: qpath(p, bow(p, q, 31 * i + 11, 9), q)
          }));
        });

        S.trailBox = ctx.svgEl("g", {});
        svg.appendChild(S.trailBox);

        POS.forEach(function (p, i) {
          const c = ctx.svgEl("path", {
            "class": "anim-node-off bc-blob", d: blob(p[0], p[1], R, 13 * i + 5)
          });
          svg.appendChild(c);
          const t = ctx.svgEl("text", {
            "class": "anim-label bc-name", x: p[0], y: p[1] + 6,
            "text-anchor": "middle"
          });
          t.textContent = NAME[i];
          svg.appendChild(t);
          S.nodes.push(c);

          const b = ctx.svgEl("text", {
            "class": "anim-label bc-badge", x: BADGE[i][0], y: BADGE[i][1],
            "text-anchor": "middle"
          });
          b.textContent = String(S.tally[i]);
          svg.appendChild(b);
          S.badges.push(b);
        });

        box.appendChild(svg);

        const line = ctx.el("div", "anim-tally");
        line.innerHTML = "<span>routes counted</span><b data-bc-count>" +
          S.done + " / " + PAIRS.length + "</b>";
        box.appendChild(line);
        S.counter = line.querySelector("[data-bc-count]");
      }

      function lite(i, on) {
        S.nodes[i].setAttribute("class",
          (on ? "anim-node" : "anim-node-off") + " bc-blob");
      }

      function bump(i) {
        S.tally[i] += 1;
        S.badges[i].textContent = String(S.tally[i]);
        S.badges[i].classList.add("bc-bump");
        setTimeout(function () { S.badges[i].classList.remove("bc-bump"); }, 520);
      }

      /* `silent` replays an earlier pair for its points without the theatre. */
      async function route(idx, silent, speed) {
        const pr = PAIRS[idx];
        const chain = [pr[0]].concat(pr[2], [pr[1]]);

        if (silent || ctx.fast()) {
          pr[2].forEach(bump);
          S.counter.textContent = (++S.done) + " / " + PAIRS.length;
          return;
        }

        lite(pr[0], true);
        lite(pr[1], true);

        let d = "";
        for (let i = 0; i < chain.length - 1; i++) {
          const g = S.geo[key(chain[i], chain[i + 1])];
          const fwd = g.p === POS[chain[i]];
          const a = fwd ? g.p : g.q, b = fwd ? g.q : g.p;
          d += (i === 0 ? "M" + a[0] + " " + a[1] : "") +
               "Q" + g.c[0].toFixed(1) + " " + g.c[1].toFixed(1) +
               " " + b[0] + " " + b[1];
        }
        const p = ctx.svgEl("path", { "class": "anim-trail", d: d });
        S.trailBox.appendChild(p);

        const len = p.getTotalLength();
        p.style.strokeDasharray = len;
        p.style.strokeDashoffset = len;
        p.getBoundingClientRect();               /* commit before transition */
        p.style.transition = "stroke-dashoffset " + (speed || 900) + "ms ease-out";
        p.style.strokeDashoffset = "0";

        await ctx.sleep(speed || 900);
        pr[2].forEach(bump);
        S.counter.textContent = (++S.done) + " / " + PAIRS.length;

        await ctx.sleep(speed && speed < 500 ? 150 : 900);
        p.remove();
        lite(pr[0], false);
        lite(pr[1], false);
      }

      function crown() {
        S.nodes[WINNER].setAttribute("class", "anim-node bc-blob bc-win");
        S.badges[WINNER].classList.add("bc-win-badge");
        const big = ctx.el("div", "anim-big");
        big.textContent = "14 / 36";
        big.style.textAlign = "center";
        box.appendChild(big);
        const cap = ctx.el("div", "anim-caption");
        cap.textContent = "D is in the middle of more journeys than anyone else here.";
        cap.style.textAlign = "center";
        box.appendChild(cap);
      }

      return { build: build, route: route, crown: crown };
    }
  });
});
