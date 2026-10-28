\version "2.26.0"
% Notes overlapping in one voice: << >> without \\ keeps one voice
% (Mutopia's Clair de lune, bar 14); a bass drawn as a dotted half, held
% under the rest of its voice (bar 64).
\score {
  \new Staff {
    \time 3/4
    << b2. { s8 <f' b'>8 ~ <f' b'>2 } >> |
    ees2.*1/2 ees'4. |
    c'2. |
  }
  \layout { }
}
