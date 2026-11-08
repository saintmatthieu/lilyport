\version "2.26.0"
% \cresc and \endcresc as sources before 2.13.20 wrote them, renamed by
% convert-ly (compat.ly), as in Diabelli's Op. 149 No. 6.
\score {
  \new Staff \relative c' {
    c4 d \deprecatedcresc e f | g2 \deprecatedendcresc a \deprecateddim | g1 \deprecatedenddim
  }
  \layout { }
}
