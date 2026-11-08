\version "2.26.0"
% A title page and a note between the scores of a book, as top-level
% markups: they share the book's list of scores, without music.
\markup \fill-line { "Exercises" }
\score {
  \new Staff \relative c' { c4 d e f }
  \layout { }
}
\markup \italic "This piece has been attributed to someone else."
\bookpart {
  \markup "Part two"
  \score {
    \new Staff \relative c'' { g1 }
    \layout { }
  }
}
