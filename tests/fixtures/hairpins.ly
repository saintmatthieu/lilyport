\version "2.26.0"
% Hairpins that overlap on one staff: a spacer voice carrying one "to give
% it a nicer length" and a voice of marks only (Mutopia's Chopin Op. 28
% No. 4, bar 16); hairpins ended by the next one and by a dynamic.
\score {
  \new Staff <<
    \new Voice {
      << { b'8. ais'16 ais'4 } \\ { s16\< s s s s s\! s s } >> gis''4\> fis''8. e''16\! |
      e''8\f\< dis'' c''' dis''\> e'' g'' b'4\p |
      c''1 |
    }
    \new Voice { s4 s8\> s s2 | s1 | s2 s4\! s4 | }
  >>
  \layout { }
}
