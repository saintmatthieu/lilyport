%% This file is part of lilyport.
%%
%% Copyright (C) 2026 Matthieu Hodgkinson
%%
%% This program is free software: you can redistribute it and/or modify
%% it under the terms of the GNU General Public License as published by
%% the Free Software Foundation, either version 3 of the License, or
%% (at your option) any later version.
%%
%% This program is distributed in the hope that it will be useful,
%% but WITHOUT ANY WARRANTY; without even the implied warranty of
%% MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
%% GNU General Public License for more details.
%%
%% You should have received a copy of the GNU General Public License
%% along with this program. If not, see <https://www.gnu.org/licenses/>.

%% For the tests: gives every score without a \midi block the default one,
%% so that LilyPond writes its own MIDI of it, to compare lilyport's
%% MusicXML with (rendered by another program). Loaded like the listener.

\version "2.24.0"

#(define (lilyport-add-midi book)
   (for-each lilyport-add-midi (ly:book-book-parts book))
   (for-each
    (lambda (score)
      (if (not (any (lambda (def) (eq? (ly:output-def-lookup def 'output-def-kind #f) 'midi))
                    (ly:score-output-defs score)))
          (ly:score-add-output-def! score (ly:output-def-clone $defaultmidi))))
    (ly:book-scores book)))

#(let ((handler toplevel-book-handler))
   (set! toplevel-book-handler
         (lambda (book . rest)
           (lilyport-add-midi book)
           (apply handler book rest))))
