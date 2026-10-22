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

%% Before beamExceptions (2.12 and earlier): #(override-auto-beam-setting ...),
%% #(revert-auto-beam-setting ...). Beaming isn't exported: nothing.
#(define-public (override-auto-beam-setting . args)
   (make-music 'SequentialMusic 'elements '()))
#(define-public (revert-auto-beam-setting . args)
   (make-music 'SequentialMusic 'elements '()))
