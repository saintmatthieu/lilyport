\version "2.26.0"
\score {
  \new PianoStaff <<
    \new Staff = "up" \relative c'' {
      \time 3/4 \key g \major
      << { d4 g,8 a b c } \\ { b4 g2 } >> |
      \tuplet 3/2 { d8 e fis } \grace a16 g2 ~ | g2.
    }
    \new Staff = "down" \relative c { \clef bass g4 <b d> q | c2 d4 | g,2. }
  >>
  \layout { }
}
