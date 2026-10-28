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


%% For the tests: plays every score's \repeat volta and \repeat segno
%% unfolded (\unfoldRepeats), so that LilyPond's MIDI plays the repeats, as
%% a reader of lilyport's MusicXML does. Loaded like the listener. Repeats
%% set by hand (repeatCommands) stay played once.

\version "2.24.0"

#(define (lilyport-forget-lengths music)
   "Unsets the lengths the parser cached on MUSIC's expressions that hold
others: after unfolding they are the folded lengths (the unfolded repeats
copy theirs too), and LilyPond would stop playing there."
   (let ((elements (ly:music-property music 'elements))
         (element (ly:music-property music 'element)))
     (if (or (pair? elements) (ly:music? element))
         (ly:music-set-property! music 'length '()))
     (for-each lilyport-forget-lengths elements)
     (if (ly:music? element) (lilyport-forget-lengths element))))

#(define (lilyport-unfold-repeats book)
   (for-each lilyport-unfold-repeats (ly:book-book-parts book))
   (for-each
    (lambda (score)
      (let ((music (ly:score-music score)))
        ;; Unfolded in place, except a repeat at the top, which becomes a new
        ;; expression the score doesn't hold.
        (if (eq? (unfold-repeats '(volta segno) music) music)
            (lilyport-forget-lengths music)
            (ly:warning "lilyport: a \\repeat at the top of a score: not unfolded"))))
    (ly:book-scores book)))

#(let ((handler toplevel-book-handler))
   (set! toplevel-book-handler
         (lambda (book . rest)
           (lilyport-unfold-repeats book)
           (apply handler book rest))))
