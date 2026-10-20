#!/bin/sh
# side-by-side ASCII dump of pictures matching a regex: games/smb/dump.sh '^player_small' [per row]
python -m games.smb.sheet txt "$1" | python -c "
import sys
n=int(sys.argv[1]); blocks=[];cur=None
for l in sys.stdin.read().split('\n'):
    if l.startswith('@'): cur=[l[2:]];blocks.append(cur)
    elif cur is not None and l: cur.append(l)
for i in range(0,len(blocks),n):
    band=blocks[i:i+n]; h=max(len(b) for b in band)
    for b in band: print('@', b[0], len(b[1]), 'x', len(b)-1)
    for y in range(1,h):
        print(' '.join((b[y] if y<len(b) else '').ljust(len(b[1])) for b in band))
    print()
" ${2:-7}
