\version "2.26.0"
% A score for print and one for MIDI that unfolds its repeats the way sources
% before 2.18 did, with the one-argument unfold-repeats (compat.ly).
music = \relative c'' { \repeat volta 2 { c4 d e f } g1 }
\score {
  \new Staff \music
  \layout { }
}
\score {
  \new Staff \applyMusic #unfold-repeats \music
  \midi { }
}
\score {
  \new Staff \unfoldRepeats \music
  \midi { }
}
