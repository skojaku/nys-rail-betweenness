# The bottleneck is still the portage

Betweenness centrality on the rail network of upstate New York. **The six most
central towns are all Erie Canal towns** — Syracuse, Rome, Buffalo, Utica,
Little Falls, Rochester. 7th and 8th (Batavia, Johnstown) are not on the canal.

→ **[Read the page](https://skojaku.github.io/nys-rail-betweenness/)**

It is not a size effect: Rome ranks 2nd with 3 rail connections while Buffalo
has 10 and ranks 3rd. The two small towns near the top, Rome and Little Falls,
are both pre-canal portages — the Oneida Carry and the Mohawk gorge. Both were
canalised in the 1790s (Little Falls 1795, five locks around a 44-foot drop;
Rome 1797, 1.7 miles and two locks across the carry), a generation before the
Erie.

12 of the 35 towns sit on the Erie Canal main line. The top six are six of those
twelve.

## What is measured

Present-day OpenStreetMap track for upstate New York (the state minus the five
NYC boroughs, Nassau, Suffolk, Westchester, Rockland). Junctions are contracted
so **each town is a single vertex**, and betweenness runs over town-to-town
traffic: the score is the share of journeys between other towns that pass
through this one. Shortest paths are weighted by track length — this is
geometry, not timetables.

The towns are New York's 53 incorporated cities outside those downstate
counties, taken from the state's list, not picked along a rail line; 35 of them
end up with a vertex on the contracted network.

## Caveats worth knowing

- Ranks 5–8 (.121 .119 .112 .109) are within noise. The claim is the *set*, not
  the order.
- Canal cities are over-represented among the 35: 12 of the 13 Erie main-line
  cities have a rail vertex (92%) against 23 of 40 others (58%). Only Cohoes
  drops out. So the top six being canal towns is partly a head start.
- A junction joins a town within 10 km of its boundary. At strict city limits
  Rochester scores exactly zero: the shortest Buffalo→Syracuse route takes the
  CSX **West Shore Subdivision**, which passes about 2 km south of the city
  boundary, rather than the CSX Rochester Subdivision that runs through the city
  — 232.5 km against 235.3 km, a 1.2% saving. Below 10 km the ranking measures
  whether a through route happens to cross a municipal boundary, not rail
  importance.
- Track is filtered to `railway=rail` without a `service` tag. Filtering on
  `usage=main|branch` instead shatters the network, because US `usage` tagging
  is uneven.

## Reproducing

```bash
pip install osmnx networkx igraph geopandas matplotlib pandas
python scripts/upstate_betweenness.py --filter through   # downloads + scores junctions
python scripts/town_betweenness.py --buffer-km 10        # contracts to towns
```

`data/town_betweenness_10km.csv` is the town ranking;
`data/city_betweenness_upstate_through.csv` is the junction-level aggregate it
was derived from.

Page styling reuses the design tokens of
[adv-net-sci](https://github.com/skojaku/adv-net-sci)'s lecture notes
(`lecture-note/m01-euler_tour/pen-and-paper/lecture-hall.css`), including its
rule that the hand is in the lines, not in the letters.
