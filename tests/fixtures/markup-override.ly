\version "2.26.0"
% A text with an \override of a markup property (Beethoven's Pathétique,
% Chopin's Ballade No. 1): its property is a pair, not a list.
\score {
  \new Staff \relative c'' {
    c4^\markup \override #'(baseline-skip . 1) \column { "dolce" "e legato" } d e f
  }
  \layout { }
}
