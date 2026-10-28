\version "2.26.0"
% Scaled durations outside \tuplet (Moonlight: a8*2/3 dis4*2/3), a
% trill's resolution written with \afterGrace (Snortum's Nocturne), and a
% quarter drawn in an eighth's time before a skip (Mutopia's Rondo alla turca).
\score {
  \new Staff \relative c'' {
    \time 2/4
    a8*2/3 b4*2/3 c8*2/3 d e |
    \afterGrace f4.\trill { e16 f } g8 | a2 |
    c4*1/2 s8 a8 b |
  }
  \layout { }
}
