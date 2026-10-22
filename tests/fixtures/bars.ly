\version "2.26.0"
% A pickup, a multi-measure rest, a cadenza and a final bar line.
\score {
  \new Staff \relative c'' {
    \time 3/4 \partial 4 g4 | c2. | R2.*2 |
    \cadenzaOn c8 d e f g a b c \cadenzaOff \bar "|"
    c,2. \bar "|."
  }
  \layout { }
}
