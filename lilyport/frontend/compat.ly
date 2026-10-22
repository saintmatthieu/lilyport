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

%% Definitions that old LilyPond sources rely on and that convert-ly doesn't
%% rewrite (Scheme calls within the music), in terms of what replaced them.
%% Loaded before the score with -dinclude-settings. Mutopia's catalogue spans
%% two decades of LilyPond: add to this as its sources need it.

\version "2.24.0"

%% Before \ottava (2.12 and earlier): #(set-octavation n)
#(define-public (set-octavation octave)
   (make-music 'OttavaEvent 'ottava-number octave))

%% Before beamExceptions (2.12 and earlier): #(override-auto-beam-setting
%% '(end * * * *) N D [context]) ended automatic beams at N/D in the bar;
%% several calls add up. In today's terms: beats of the largest length that
%% divides every end and the bar (exact when the ends are evenly spaced, as in
%% '(end ...) 1 4, 2 4, 3 4). Settings other than 'end, and the beam and time
%% signature filters (the *s), are not translated.
#(define lilyport-beam-ends (make-weak-key-hash-table))
#(define (lilyport-rational-gcd a b)
   (/ (gcd (* (numerator a) (denominator b)) (* (numerator b) (denominator a)))
      (* (denominator a) (denominator b))))
#(define-public (override-auto-beam-setting setting num den . rest)
   (if (eq? (car setting) 'end)
       (context-spec-music
        (make-apply-context
         (lambda (context)
           ;; Lengths are moments before 2.25 (baseMoment), numbers since (beatBase).
           (let* ((ends (cons (/ num den) (hashq-ref lilyport-beam-ends context '())))
                  (length (ly:context-property context 'measureLength 1))
                  (moments? (ly:moment? length))
                  (measure (if moments? (ly:moment-main length) length))
                  (beat (fold lilyport-rational-gcd measure ends)))
             (hashq-set! lilyport-beam-ends context ends)
             (if moments?
                 (ly:context-set-property! context 'baseMoment (ly:make-moment beat))
                 (ly:context-set-property! context 'beatBase beat))
             (ly:context-set-property! context 'beatStructure
                                       (make-list (inexact->exact (/ measure beat)) 1))
             (ly:context-set-property! context 'beamExceptions '()))))
        (if (pair? rest) (car rest) 'Voice))
       (make-music 'SequentialMusic 'elements '())))
#(define-public (revert-auto-beam-setting . args)
   (make-music 'SequentialMusic 'elements '()))
