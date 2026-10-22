\version "2.26.0"
% What is attached to notes, and directions.
\header { title = "Markings" composer = "Nobody" copyright = "Public Domain" }
\score {
  \new Staff \relative c' {
    c4\p( d-. e-> f) | <c~ e-3>2 <c e>2\fermata |
    c4\< d e f\! | g2\sustainOn^"dolce" g2\sustainOff\trill |
  }
  \layout { }
}
