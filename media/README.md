# media/

Drop edited screen recordings here, named after the page they belong to:

    media/octopuses.mov   ->   public/images/gifs/octopuses.gif   ->   card for /octopuses

Then run:

    python3 scripts/gifify.py

Only new or changed clips are rebuilt. The videos in this folder are not
committed; the GIFs the script produces are.
