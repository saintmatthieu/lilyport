\version "2.26.0"
% The \text markup command of sources until 2.18 (compat.ly), in a dynamic
% made of a markup, as in Czerny's Op. 821 No. 19.
pdolce = #(make-dynamic-script (markup #:dynamic "p" #:text #:italic "dolce"))
\score {
  \new Staff \relative c'' { c4\pdolce d e f }
  \layout { }
}
