# The bottleneck is still the portage

Betweenness centrality on New York State's in-state rail network. **The six most
central towns are all Erie Canal towns** — Syracuse, Rome, Buffalo, Utica,
Little Falls, Rochester. 7th and 8th (Batavia, Johnstown) are not on the canal.

→ **[Read the page](https://skojaku.github.io/nys-rail-betweenness/)**

It is not a size effect: Rome ranks 2nd with 3 rail connections while Buffalo
has 10 and ranks 3rd. The two small towns near the top, Rome and Little Falls,
are both pre-canal portages — the Oneida Carry and the Mohawk gorge. Both were
canalised in the 1790s, decades before the Erie.

12 of the 35 towns sit on the canal, so six-for-six by chance is 1 in 1,757.

## What is measured

Present-day OpenStreetMap track for upstate New York (the state minus the five
NYC boroughs, Nassau, Suffolk, Westchester, Rockland). Junctions are contracted
so **each town is a single vertex**, and betweenness runs over town-to-town
traffic: the score is the share of journeys between other towns that pass
through this one. Shortest paths are weighted by track length — this is
geometry, not timetables.

## Caveats worth knowing

- Ranks 5–8 (.121 .119 .112 .109) are within noise. The claim is the *set*, not
  the order.
- A junction joins a town within 10 km of its boundary. At strict city limits
  the CSX main line runs ~3 km outside Rochester, and Rochester scores exactly
  zero — Buffalo→Syracuse round the bypass is 232 km against 235 km through it.
  Below 10 km the ranking measures whether a main line happens to cross a
  municipal boundary, not rail importance.
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
