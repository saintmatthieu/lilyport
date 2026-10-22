\version "2.26.0"
\header {
  title = "Top-level title"
  composer = \markup \bold "A. Composer"
  copyright = "Public Domain"
}
\book {
  \header { title = "Book title" }
  \score { { c'1 } \midi { } }
  \score { \header { piece = "First" } { c'1 } \layout { } }
  \score { \header { title = "Second" } { d'1 } }
}
\book {
  \bookpart { \header { title = "Part 1" } \score { { e'1 } } }
  \bookpart { \header { title = "Part 2" } \score { { f'1 } } }
}
