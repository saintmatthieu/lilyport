\version "2.26.0"
% Marks drawn as text, as in Mutopia's Nocturne, and a hidden metronome mark.
ped = _\markup \small { \musicglyph "pedal.Ped" "." }
pes = _\markup \small { \musicglyph "pedal.*" }
grc = ^\markup \column { "12121" \flat \musicglyph "scripts.turn" \natural }
\score {
  \new Staff \relative c'' {
    \override Score.MetronomeMark.transparent = ##t
    \tempo 8 = 132
    c4\ped d\grc e\pes^"54" f\ped | g\ped a b\pes c |
  }
  \layout { }
}
