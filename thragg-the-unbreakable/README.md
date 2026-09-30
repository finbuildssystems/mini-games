# Thragg the Unbreakable vs. the Fursworn

A 3D arena slaughter game. You are Thragg the Unbreakable, a one-eyed orc warlord holding the Iron Wastes of Gorrakh against the Fursworn: an invading cult of people in cheap animal suits who came through a tear in the sky and want, more than anything, to hug you. Some of your own brothers have joined them.

Each round has a timer and a kill quota. Meet the quota and a named mini-boss arrives (Steve, Jeffrey, Alexander, Nigel). Kill him and you unlock a new weapon and choose a boon. Survive four rounds and you face Gary, Alpha of the Fursworn.

Every character is built from separate body parts, so heads, arms, legs and torsos come off, fly, bounce and bleed onto the floor.

## How to run it

Serve the repository folder with a local web server and open the game from there. It needs an internet connection the first time, because the Three.js library is loaded from a CDN. (Opening `index.html` straight from the file system works in some browsers, but most block the sound files from loading that way.)

```bash
python3 -m http.server 8000
```

and open <http://localhost:8000/thragg-the-unbreakable/>.

## Controls

The game is played in first person: you look out through Thragg's one good eye, with his arms and the two-handed axe in front of you. Click the game once to capture the mouse; Esc releases it (the game pauses until you click again).

| Key | Action |
| --- | --- |
| W A S D | Move (relative to where you are looking) |
| Mouse | Look |
| Left click | Swing the axe. Three swings chain into an overhead chop. |
| Q | Whirlwind: spin and cleave everything around you (cooldown) |
| Space | Lunge: a short burst of speed; you cannot be hit while lunging |
| E or right click | Axe throw. Pierces several enemies and returns. Unlocked after round 1. |
| 1 (hold) | The Shoota. Unlocked after round 2. |
| 2 (hold) | The Burna. Unlocked after round 3. |
| 3 | The Rokkit Launcha. Unlocked after round 4. |

Kills heal you a little. Blood is a resource. Only kills Thragg makes himself count towards the quota: enemies that walk into molten iron or get caught in an exploding drum are their own problem.

## Rounds

| Round | Quota | Arena | Mini-boss |
| --- | --- | --- | --- |
| 1 | 10 | The Scrap Gate | Steve |
| 2 | 20 | The Bone Yard | Jeffrey |
| 3 | 30 | The Forge Pits (molten iron melts anyone who steps in it) | Alexander |
| 4 | 40 | The Rift Altar | Nigel |
| 5 | — | The Rift Altar | Gary, Alpha of the Fursworn |

Meeting the quota adds 20 seconds to the clock for the mini-boss. Run out of time, or health, and it is over.

## Built with

- [Three.js](https://threejs.org/) r160, loaded from jsDelivr. Everything else is in `index.html`: the characters, the arenas, the war drums and the gore.
- Recorded sound effects in `sounds/` (about 1.4 MB), all from [OpenGameArt](https://opengameart.org/):
  - **Aargh! (male screams)** by congusbongus, CC-BY 3.0 — an aggregation of *Helmut Scream* by creativeheroes (CC-BY 3.0), *Male_Thijs_loud_scream* by thanvannispen (CC-BY 3.0) and *human male scream multi* by JohnsonBrandEditing (CC0). See `sounds/CREDITS-aargh.txt`. [Source](https://opengameart.org/content/aargh-male-screams)
  - **80 CC0 creature SFX** by rubberduck, CC0. [Source](https://opengameart.org/content/80-cc0-creature-sfx)
  - **Swishes Sound Pack** by artisticdude, CC0 (converted to AAC). [Source](https://opengameart.org/content/swishes-sound-pack)
  - **25 CC0 bang / firework SFX** by rubberduck, CC0. [Source](https://opengameart.org/content/25-cc0-bang-firework-sfx)
  - **Squish Sounds Effects** by EZduzziteh, CC0. [Source](https://opengameart.org/content/squish-sounds-effects)
  - **Fireplace Sound loop** by PagDev, CC0 (a 3.5-second slice, converted to AAC). [Source](https://opengameart.org/content/fireplace-sound-loop)
- Keyboard and mouse only for now. Touch controls for iPad and iPhone are planned.
- Thragg shouts on kill streaks, whirlwinds and boss arrivals; enemies get last words as they die.

## Testing shortcuts

Add these to the address bar if you want to jump about while tweaking things: `?round=3` starts at round 3 with the earlier weapons unlocked, `?god` makes Thragg unkillable and multiplies his damage, `?third` switches to the older third-person camera, `?nolock` skips mouse capture (for automated testing). For example `index.html?round=5&god`.
