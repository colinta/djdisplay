#!/bin/bash
mpc idleloop player | while read event; do
    # Grab current track metadata
    artist="$(mpc current -f '%artist%')"
    title="$(mpc current -f '%title%')"
    album="$(mpc current -f '%album%')"
    echo "$artist / $album / $title"
done
