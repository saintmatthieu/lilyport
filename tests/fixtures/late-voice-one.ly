\version "2.26.0"
% The upper voice (\voiceOne) begins after the lower one (Moonlight's melody).
\score {
  \new Staff <<
    \new Voice = "low" { \voiceTwo c'1 | c'1 }
    \new Voice = "high" { \voiceOne s1 | g''1 }
  >>
  \layout { }
}
