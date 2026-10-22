\version "2.26.0"
% The heading as the starting tempo, at the \midi block's tempo; a \tempo
% mark instead when there is one.
\header { piece = "Adagio sostenuto" }
\score { { c'1 } \layout { } \midi { \tempo 4 = 54 } }
\score { { \tempo "Allegro" 4 = 132 c'1 } \layout { } }
