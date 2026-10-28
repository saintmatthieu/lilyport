\version "2.26.0"
% A score engraved without \midi, its MIDI from a twin score with only a
% \midi (Mutopia's Entertainer: the twin unfolds the repeats).
music = { \tempo "Not fast" c'1 }
\score { \music \layout { } }
\score { \unfoldRepeats \music \midi { \tempo 4 = 72 } }
