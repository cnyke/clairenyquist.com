# Scripted card videos

Each script drives its page in headless Chrome (deterministic, eased,
30 fps, retina), bakes in the boomerang loop, and writes the card video
to public/videos/. Run from the repo root after `npm run build` (they
serve and capture the built site in dist/):

    python3 scripts/captures/nonhuman-neighbors.py

Requires scripts/png2mp4 (swiftc -O scripts/png2mp4.swift -o scripts/png2mp4).
Re-run a script whenever its page changes so the card matches the live piece.
The octopuses, malaria, meps, themet, music, respiratoryviruses,
tuberculosis, torus, and wilddyeplants cards use hand-recorded clips
instead, converted with scripts/videoify.py.
