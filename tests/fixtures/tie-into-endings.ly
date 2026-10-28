\version "2.26.0"
% A tie at the end of the repeated music, into both endings (Mutopia's
% Entertainer, bars 90-92: no \repeatTie on the second), and one with
% \repeatTie.
\score {
  \new Staff \relative c'' {
    \time 2/4
    \repeat volta 2 { c4 d | e2 ~ | } \alternative { { e2 } { e4 f } }
    \repeat volta 2 { g4 a | <b d>2 ~ | } \alternative { { <b d>2 } { <b d>4\repeatTie c } }
    \bar "|."
  }
  \layout { }
}
