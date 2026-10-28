\version "2.26.0"
% Repeat signs and voltas set by hand (repeatCommands), which LilyPond plays
% once (\unfoldRepeats leaves them).
\score {
  \new Staff \relative c'' {
    \time 2/4
    c4 d |
    \set Score.repeatCommands = #'(start-repeat)
    d4 e |
    \set Score.repeatCommands = #'((volta "1"))
    f2 |
    \set Score.repeatCommands = #'((volta #f) (volta "2") end-repeat)
    g2 |
    \set Score.repeatCommands = #'((volta #f))
    a2 \bar "|."
  }
  \layout { }
}
