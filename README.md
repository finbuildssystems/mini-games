# Mini games

Little games and creative experiments made with AI helpers (Claude, Codex). Kept separate from the iQ apps on purpose: nothing here touches app code, and none of the app repository's checks or rules apply.

## Projects

| Folder | What it is | How to open it |
| --- | --- | --- |
| [`iq-the-best-comic`](iq-the-best-comic/) | A 30-second animated scene built from the *iQ The Best!* comic cover: the shop that never has any stock. | Open `iq-the-best-motion-comic.html` through a local web server (see its README), or view the published version on claude.ai. |
| [`thragg-the-unbreakable`](thragg-the-unbreakable/) | A 3D arena slaughter game: a one-eyed orc warlord against a cult of people in animal suits. Timed rounds, kill quotas, named mini-bosses, dismemberment. | Open `index.html` in a browser (needs internet for Three.js). Keyboard and mouse. |

## Adding a new game

1. Make a new folder with a short lowercase name, for example `space-dodger/`.
2. Put everything the game needs inside that folder, with a `README.md` saying what it is and how to play or run it.
3. Add a row to the table above.

Games that run straight in a web browser (a single `index.html`) are the easiest to keep, share and come back to.
