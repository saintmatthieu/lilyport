\version "2.26.0"
% Scaled durations outside \tuplet (Moonlight: a8*2/3 dis4*2/3), and a
% trill's resolution written with \afterGrace (Snortum's Nocturne).
\score {
  \new Staff \relative c'' {
    \time 2/4
    a8*2/3 b4*2/3 c8*2/3 d e |
    \afterGrace f4.\trill { e16 f } g8 | a2 |
  }
  \layout { }
}
