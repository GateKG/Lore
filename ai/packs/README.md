# The packs

One small text file per game, read by the tome's own hands and never by a
model. The file's name is the game's display name, lowercased, spaces
removed: `Rocket League` -> `rocketleague`, and both the `hearthstone` and
`hearthstoneheroesofwarcraft` folders resolve to `hearthstone` because the
tome merges them into one name before it looks.

## `<game>.txt` - the sound vocabulary

One line per sound the ears should listen for, `kind: what it sounds like`
in plain words. A pack REPLACES the default prompts, so a game that only
ever cheers gets only `cheer`.

## `<game>.ocr.txt` - what the screen prints

One regex per line, matched against the text the HUD reader lifts off a
frame. Two kinds of line share the file:

    kind: regex
    outcome.kind: regex with named groups

A plain line is a SENSE. When its regex matches a frame the reader writes
one event (`kind`, the matched words, one per kind per twenty seconds),
and that event becomes a tick on the bar beside the ears' own. Twelve
letters of the kind are kept.

A typed line - the head `outcome.` before the kind - is the VERDICT. It is
never an event, never deduped, never merged into the marks. The reader
returns every frame it matched on, with the named groups, and the app
folds those frames into one outcome with a span (`sns.outcomes`): the
time it first stood, the time it left, how many frames it stood on, and
whose it was. The head is split off before the twelve-letter cut, so
`outcome.placement` is `placement`, not `outcome.plac`.

The kinds the app knows how to fold:

- `win`, `loss`, `death` - the verdict itself. Named group `team` (Rocket
  League's colour) says which side; the podium says whose.
- `placement` - `n`, the place (1..8).
- `score` - `b` and `o`, both digits; only written when both were read.
- `rating` - `r` the rating and `d` its change (`+12`, `-11`).
- `clock` - `m` and `s`; a reading under a minute on the grid is where a
  match is about to end. A trigger, not an outcome.

A pack may add trigger words of its own under the same head (`overtime`,
`podium`, `spectator`, `lobby`); the app reads them for where to look and
whose win it was, and they never reach the bar on their own.

Match the game's exact words. `WINNER` alone is a player's title on a
goal replay; `WINNER` followed by `BLUE` or `ORANGE` on the same frame is
the end of a match. `Place` after an ordinal is a Battlegrounds result;
bare `win` is a Discord channel read off an alt-tab.

`#` opens a comment. A line the regex engine cannot compile is skipped,
never fatal: a pack fails open, like everything else the reader does.
