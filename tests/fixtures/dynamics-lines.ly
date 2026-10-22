\version "2.26.0"
% Dynamics lines (\new Dynamics) between and under the staves, as in
% Knute Snortum's engravings: their marks belong to the staff above them.
\score {
  \new PianoStaff <<
    \new Staff = "upper" \relative c'' { c2 d | e1 }
    \new Dynamics { s2\p\< s\! | s1^"cresc." }
    \new Staff = "lower" \relative c { \clef bass c1 | c1 }
    \new Dynamics { s2\sustainOn s\sustainOff | s1 }
  >>
  \layout { }
}
