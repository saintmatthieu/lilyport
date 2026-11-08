\version "2.26.0"
% The spacing convert-ly writes for a source before 2.13.x, in a score's
% \layout (Beethoven's Moonlight Sonata, 3rd movement): staff-space is
% compat.ly's there.
\score {
  \new Staff \relative c'' { c4 d e f }
  \layout {
    obsolete-between-system-padding = #0.1
    system-system-spacing.padding = #(/ obsolete-between-system-padding staff-space)
  }
}
