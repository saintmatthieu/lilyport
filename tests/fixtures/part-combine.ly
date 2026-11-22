\version "2.26.0"
% Two parts on one staff by \partCombine (Mutopia's Hall of the Mountain
% King, right hand): chords where their rhythms agree (bar 1, beats 1-2),
% two voices where they don't (beat 3), one part alone (bar 2), a bar's rest
% in both (bar 3), a unison (bar 4).
\score {
  \new Staff \with { printPartCombineTexts = ##f } {
    \time 4/4
    \partCombine
      { e''4 d'' c''8 d'' e''4 | g''2 r2  | R1 | c''1 }
      { c''4 b'  a'4      c''4 | e''2 g'2 | R1 | c''1 }
  }
  \layout { }
}
