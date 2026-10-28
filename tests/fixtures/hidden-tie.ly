\version "2.26.0"
% A tie from one voice to another, which LilyPond can't draw: the edition
% draws it to a hidden note (Mutopia's Entertainer, bar 69).
\score {
  \new Staff {
    \time 2/4
    << { <c'' c'>8. <g'' bes'>16 ~ g''4 }
       \\ { s8. \hideNotes bes'4*1/4 ~ \unHideNotes bes'8 bes' } >> |
  }
  \layout { }
}
