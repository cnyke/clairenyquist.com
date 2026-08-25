# Scripted card animations

Every animated card ships two builds of the same clip: a retina H.264
video in public/videos/ (desktops swap it in at load) and an animated
WebP in public/images/gifs/ (touch devices; animated WebP keeps moving
even on phones in low power mode, which block video autoplay). Both are
committed, along with the first-frame poster at <slug>-poster.webp.

Each script here drives its page in headless Chrome (deterministic,
eased, 30 fps, retina) and writes the MP4. Run from the repo root after
`npm run build` (they serve and capture the built site in dist/):

    python3 scripts/captures/nonhuman-neighbors.py

Then build the WebP from that MP4 — use the card's width from the works
list, and --no-bounce because the MP4 already has the boomerang baked in:

    python3 scripts/gifify.py public/videos/nonhuman-neighbors.mp4 \
        --slug nonhuman-neighbors --width 538 --no-bounce --vivid 1.0 --force

Requires scripts/png2mp4 (swiftc -O scripts/png2mp4.swift -o scripts/png2mp4).
Re-run a script whenever its page changes so the card matches the live piece.
The octopuses, malaria, meps, themet, music, respiratoryviruses,
tuberculosis, torus, and wilddyeplants cards use hand-recorded clips
instead (media/*.mov -> videoify.py -> the same gifify.py step). genes.py
is self-serving: it renders its SVG layers directly, no build needed.
