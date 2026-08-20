/* ==========================================================================
   betweenness.js — counting the journeys that pass through a town.

   A scene array for the shared kit (assets/anim.css + assets/anim.js); it
   carries no sequencer and no copy of the kit's stylesheet. See the header of
   assets/anim.js for the contract.

   Six towns and five lines, and nothing cleverer than that. The temptation was
   to build a shape that also proves the page's other point — that a town with
   two lines can outscore a town with ten — but a topology bent to make a second
   argument stops being an example of the first. The counting is the whole
   lesson here; the small-town result is in the page text, with real numbers.

   Being a tree, every pair has exactly one route, so no scene has to explain
   ties. The fifteen pairs and their middles are written out below rather than
   searched at page load.
   ========================================================================== */

(window.animReady = window.animReady || []).push(function () {

  /* ---------------------------------------------------------------- data --- */
  const NAME = ["A", "B", "C", "D", "E", "F"];
  const POS = [[52, 176], [150, 120], [252, 172], [356, 114], [462, 172], [252, 52]];
  const EDGES = [[0, 1], [1, 2], [2, 3], [3, 4], [2, 5]];
  const R = 17;

  /* Where a town's running total sits, clear of every line into it. */
  const BADGE = [[52, 214], [150, 92], [252, 210], [356, 86], [462, 210], [252, 24]];

  /* All fifteen pairs, each with the towns it passes through, west to east. */
  const PAIRS = [
    [0, 1, []], [0, 2, [1]], [0, 3, [1, 2]], [0, 4, [1, 2, 3]], [0, 5, [1, 2]],
    [1, 2, []], [1, 3, [2]], [1, 4, [2, 3]], [1, 5, [2]],
    [2, 3, []], [2, 4, [3]], [2, 5, []],
    [3, 4, []], [3, 5, [2]],
    [4, 5, [3, 2]]
  ];
  const SHOWCASE = 3;   /* A to E — the longest route, three towns in the middle */
  const SECOND = 14;    /* E to F — a route that turns the corner at C */

  /* --------------------------------------------------------------- scenes */
  const scenes = [
    {
      label: "Six towns, five lines",
      note: "Betweenness asks one question: how often does a town sit in the middle of somebody else's journey?",
      async run(ctx) {
        ctx.build();
        await ctx.sleep(1600);
      }
    },
    {
      label: "Take one pair",
      note: "A to E runs through B, C and D. Each of the three picks up a point. A and E get nothing — the journey is theirs, they are not in the middle of it.",
      async run(ctx) {
        ctx.build();
        await ctx.sleep(500);
        await ctx.route(SHOWCASE);
        await ctx.sleep(2200);
      }
    },
    {
      label: "And another",
      note: "E to F turns the corner at C. Two more points, and C now has two.",
      async run(ctx) {
        ctx.build();
        await ctx.route(SHOWCASE, true);
        await ctx.sleep(600);
        await ctx.route(SECOND);
        await ctx.sleep(2200);
      }
    },
    {
      label: "Now every pair",
      note: "Fifteen pairs of towns, fifteen routes. Every town in the middle of one gets a point.",
      async run(ctx) {
        ctx.build();
        for (let i = 0; i < PAIRS.length; i++) {
          if (i === SHOWCASE || i === SECOND) continue;
          await ctx.route(i, false, 260);
        }
        await ctx.route(SHOWCASE, false, 260);
        await ctx.route(SECOND, false, 260);
        await ctx.sleep(2400);
      }
    },
    {
      label: "That is the score",
      note: "C sits on 8 of the 15 routes, B and D on 4 each, and the three end towns on none. Divide by the number of pairs and you have betweenness centrality.",
      async run(ctx) {
        ctx.build(true);
        await ctx.sleep(700);
        ctx.crown();
        await ctx.sleep(3600);
      }
    }
  ];

  mountScenes(document.getElementById("bc-anim"), scenes, {
    stepsLabel: "Betweenness steps",

    helpers(ctx) {
      const box = ctx.$("[data-anim-clear]");
      const S = { tally: [0, 0, 0, 0, 0, 0], svg: null, nodes: [], badges: [], big: null };

      const FINAL = [0, 4, 8, 4, 0, 0];

      function build(final) {
        box.textContent = "";
        S.tally = final ? FINAL.slice() : [0, 0, 0, 0, 0, 0];
        S.nodes = [];
        S.badges = [];

        const svg = ctx.svgRoot("0 0 520 246", "bc-svg");
        S.svg = svg;

        EDGES.forEach(function (e) {
          svg.appendChild(ctx.svgEl("line", {
            "class": "anim-edge",
            x1: POS[e[0]][0], y1: POS[e[0]][1],
            x2: POS[e[1]][0], y2: POS[e[1]][1]
          }));
        });

        /* The trail is drawn into its own group so a route can be wiped
           without touching the towns underneath it. */
        S.trailBox = ctx.svgEl("g", {});
        svg.appendChild(S.trailBox);

        POS.forEach(function (p, i) {
          const c = ctx.svgEl("circle", {
            "class": "anim-node-off", cx: p[0], cy: p[1], r: R
          });
          svg.appendChild(c);
          const t = ctx.svgEl("text", {
            "class": "anim-label", x: p[0], y: p[1] + 4,
            "text-anchor": "middle", "font-size": "13"
          });
          t.textContent = NAME[i];
          svg.appendChild(t);
          S.nodes.push(c);

          const b = ctx.svgEl("text", {
            "class": "anim-label bc-badge", x: BADGE[i][0], y: BADGE[i][1],
            "text-anchor": "middle", "font-size": "15"
          });
          b.textContent = String(S.tally[i]);
          svg.appendChild(b);
          S.badges.push(b);
        });

        box.appendChild(svg);

        const line = ctx.el("div", "anim-tally");
        line.innerHTML = "<span>routes counted</span><b data-bc-count>" +
          (final ? PAIRS.length : 0) + " / " + PAIRS.length + "</b>";
        box.appendChild(line);
        S.counter = line.querySelector("[data-bc-count]");
        S.done = final ? PAIRS.length : 0;
      }

      function lite(i, on) {
        S.nodes[i].setAttribute("class", on ? "anim-node" : "anim-node-off");
      }

      function bump(i) {
        S.tally[i] += 1;
        S.badges[i].textContent = String(S.tally[i]);
        S.badges[i].classList.add("bc-bump");
        setTimeout(function () { S.badges[i].classList.remove("bc-bump"); }, 420);
      }

      /* Walk the route as one stroked path, then bump the towns it crossed.
         `silent` replays an earlier pair for its points without the theatre. */
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

        const d = "M" + chain.map(function (i) {
          return POS[i][0] + " " + POS[i][1];
        }).join("L");
        const p = ctx.svgEl("path", { "class": "anim-trail", d: d });
        S.trailBox.appendChild(p);

        const len = p.getTotalLength();
        p.style.strokeDasharray = len;
        p.style.strokeDashoffset = len;
        p.getBoundingClientRect();               /* commit before transition */
        p.style.transition = "stroke-dashoffset " + (speed || 620) + "ms ease-out";
        p.style.strokeDashoffset = "0";

        await ctx.sleep(speed || 620);
        pr[2].forEach(bump);
        S.counter.textContent = (++S.done) + " / " + PAIRS.length;

        await ctx.sleep(speed ? 90 : 620);
        p.remove();
        lite(pr[0], false);
        lite(pr[1], false);
      }

      function crown() {
        S.nodes[2].setAttribute("class", "anim-node bc-win");
        S.badges[2].classList.add("bc-win-badge");
        const big = ctx.el("div", "anim-big");
        big.textContent = "8 / 15";
        big.style.textAlign = "center";
        box.appendChild(big);
        const cap = ctx.el("div", "anim-caption");
        cap.textContent = "C is on more than half of every journey in this network.";
        cap.style.textAlign = "center";
        box.appendChild(cap);
      }

      return { build: build, route: route, crown: crown };
    }
  });
});
