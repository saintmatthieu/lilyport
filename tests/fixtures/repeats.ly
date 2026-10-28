\version "2.26.0"
% Repeats: alternative endings; a section after an upbeat, its repeat signs
% in the middle of bars; a repeat played three times.
\score {
  \new Staff \relative c'' {
    \time 2/4
    \repeat volta 2 { c4 d | e f | } \alternative { { g2 } { a2 } }
    r4 \repeat volta 2 { b4 | c d | e }
    \repeat volta 3 { f4 | g a | }
    \alternative { \volta 1,2 { b2 } \volta 3 { c2 } }
    d4 e | f2 \bar "|."
  }
  \layout { }
}
