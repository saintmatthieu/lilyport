\version "2.26.0"
% A long slur in one hand while the other has short ones (the Nocturne's
% bar 2): importers pair slurs by number in file order, in the whole part.
\score {
  \new PianoStaff <<
    \new Staff \relative c'' { c2( d | e f) }
    \new Staff \relative c { \clef bass c4( d) e( f) | g( a) b( c) }
  >>
  \layout { }
}
