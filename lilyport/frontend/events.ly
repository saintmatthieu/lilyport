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

%% Writes the music LilyPond has evaluated as a stream of events, one JSON
%% object per line, for lilyport's Python side to assemble. Loaded before the
%% score with -dinclude-settings; LilyPond runs with -dno-print-pages, which
%% still translates the music (engravers included) but writes no PDF. The
%% records go to the file named by the LILYPORT_EVENTS environment variable,
%% else next to the output, as <name>.events.jsonl.
%%
%% Every record has:
%%   t      the score time, [main num, main den, grace num, grace den]
%%          (whole notes; grace time is negative before the main note)
%%   bar    currentBarNumber, pos: measurePosition (same form as t)
%%   score  which \score of the file (1-based)
%%   staff, voice
%%          ids of the contexts (numbered in order of appearance; 0 if none)
%%   kind   what happened; the other fields depend on it
%%   src    [line, column] in the source, when the event has an origin
%%
%% Each engraved score has one header record (kind "header", at time 0): its
%% fields, as text, from the \score, \bookpart, \book and top-level \header
%% blocks (an inner field hides an outer one).
%%
%% Pitches are spelled: step (0 = C ... 6 = B), alter (in whole tones, so
%% 1/2 is a sharp), octave (0 is the octave from middle C up).
%% Durations: log (0 = whole, 2 = quarter, ...), dots, factor (tuplets,
%% scaling) as [num, den].

\version "2.24.0"

#(define lilyport-port #f)
#(define lilyport-score-number 0)
#(define lilyport-context-ids (make-hash-table))
#(define lilyport-next-context-id 0)

#(define (lilyport-output-port)
   (if (not lilyport-port)
       (set! lilyport-port
             (open-output-file
              (or (getenv "LILYPORT_EVENTS")
                 (string-append (ly:parser-output-name) ".events.jsonl")))))
   lilyport-port)

#(define (lilyport-context-id ctx)
   (cond
    ((not ctx) 0)
    ((hashq-ref lilyport-context-ids ctx))
    (else
     (set! lilyport-next-context-id (1+ lilyport-next-context-id))
     (hashq-set! lilyport-context-ids ctx lilyport-next-context-id)
     lilyport-next-context-id)))

%% JSON values

#(define (json-string s)
   (call-with-output-string
    (lambda (port)
      (write-char #\" port)
      (string-for-each
       (lambda (c)
         (case c
           ((#\") (display "\\\"" port))
           ((#\\) (display "\\\\" port))
           ((#\newline) (display "\\n" port))
           ((#\tab) (display "\\t" port))
           (else (if (char<? c #\space)
                     (format port "\\u~4,'0x" (char->integer c))
                     (write-char c port)))))
       s)
      (write-char #\" port))))

#(define (json-number n)
   (if (and (exact? n) (not (integer? n)))
       (format #f "~a" (exact->inexact n))
       (format #f "~a" n)))

#(define (json-moment m)
   (format #f "[~a,~a,~a,~a]"
           (ly:moment-main-numerator m) (ly:moment-main-denominator m)
           (ly:moment-grace-numerator m) (ly:moment-grace-denominator m)))

#(define (json-fraction f)
   (format #f "[~a,~a]" (car f) (cdr f)))

#(define (json-pitch p)
   (format #f "{\"step\":~a,\"alter\":~a,\"octave\":~a}"
           (ly:pitch-notename p) (json-number (ly:pitch-alteration p))
           (ly:pitch-octave p)))

#(define (json-duration d)
   (let ((factor (ly:duration-factor d)))
     (format #f "{\"log\":~a,\"dots\":~a,\"factor\":[~a,~a]}"
             (ly:duration-log d) (ly:duration-dot-count d)
             (car factor) (cdr factor))))

#(define (json-markup m)
   (json-string
    (cond ((string? m) m)
          ((markup? m) (markup->string m))
          (else (format #f "~a" m)))))

#(define (markup-glyphs m)
   "The music glyphs a markup draws (\\musicglyph): text that stands for a
mark, such as a \"Ped.\" drawn as text rather than with \\sustainOn."
   (cond
    ((and (pair? m) (eq? (car m) musicglyph-markup) (pair? (cdr m)) (string? (cadr m)))
     (list (cadr m)))
    ((pair? m) (append-map markup-glyphs m))
    (else '())))

#(define (json-glyphs m)
   (string-append "[" (string-join (map json-string (markup-glyphs m)) ",") "]"))

#(define (json-symbol s)
   (json-string (if (symbol? s) (symbol->string s) (format #f "~a" s))))

%% Records

#(define (emit ctx event kind . fields)
   "Writes one record. FIELDS alternate names (strings) and JSON values."
   (let* ((port (lilyport-output-port))
          (origin (and event (ly:event-property event 'origin #f)))
          (location (and (ly:input-location? origin)
                         (ly:input-file-line-char-column origin))))
     (format port "{\"t\":~a,\"bar\":~a,\"pos\":~a,\"score\":~a,\"staff\":~a,\"voice\":~a,\"kind\":~a"
             (json-moment (ly:context-current-moment ctx))
             (ly:context-property ctx 'currentBarNumber 0)
             (json-moment (ly:context-property ctx 'measurePosition (ly:make-moment 0)))
             lilyport-score-number
             (lilyport-context-id (ly:context-find ctx 'Staff))
             (lilyport-context-id (ly:context-find ctx 'Voice))
             (json-string kind))
     (if location
         (format port ",\"src\":[~a,~a]" (cadr location) (caddr location)))
     (let loop ((rest fields))
       (if (pair? rest)
           (begin
             (format port ",~a:~a" (json-string (car rest)) (cadr rest))
             (loop (cddr rest)))))
     (display "}\n" port)))

#(define (event-direction event)
   (json-number (ly:event-property event 'span-direction 0)))

%% Voices: the notes and what is attached to them.

#(define lilyport-voice-engraver
   (make-engraver
    (listeners
     ((note-event engraver event)
      (let ((ctx (ly:translator-context engraver))
            (pitch (ly:event-property event 'pitch #f)))
        (apply emit ctx event "note"
               (append
                (if pitch (list "pitch" (json-pitch pitch)) '())
                (list "duration" (json-duration (ly:event-property event 'duration)))))))
     ((rest-event engraver event)
      (emit (ly:translator-context engraver) event "rest"
            "duration" (json-duration (ly:event-property event 'duration))))
     ((multi-measure-rest-event engraver event)
      (emit (ly:translator-context engraver) event "multi-measure-rest"
            "duration" (json-duration (ly:event-property event 'duration))))
     ((skip-event engraver event)
      (emit (ly:translator-context engraver) event "skip"
            "duration" (json-duration (ly:event-property event 'duration))))
     ((tie-event engraver event)
      (emit (ly:translator-context engraver) event "tie"))
     ((tuplet-span-event engraver event)
      (emit (ly:translator-context engraver) event "tuplet"
            "dir" (event-direction event)))
     ((slur-event engraver event)
      (emit (ly:translator-context engraver) event "slur" "dir" (event-direction event)))
     ((phrasing-slur-event engraver event)
      (emit (ly:translator-context engraver) event "phrasing-slur" "dir" (event-direction event)))
     ((articulation-event engraver event)
      (emit (ly:translator-context engraver) event "articulation"
            "type" (json-symbol (ly:event-property event 'articulation-type))))
     ((arpeggio-event engraver event)
      (emit (ly:translator-context engraver) event "arpeggio"))
     ((tremolo-event engraver event)
      (emit (ly:translator-context engraver) event "tremolo"
            "type" (json-number (ly:event-property event 'tremolo-type 0))))
     ((absolute-dynamic-event engraver event)
      (emit (ly:translator-context engraver) event "dynamic"
            "text" (json-markup (ly:event-property event 'text))))
     ((crescendo-event engraver event)
      (emit (ly:translator-context engraver) event "crescendo" "dir" (event-direction event)))
     ((decrescendo-event engraver event)
      (emit (ly:translator-context engraver) event "decrescendo" "dir" (event-direction event)))
     ((text-script-event engraver event)
      (emit (ly:translator-context engraver) event "text"
            "text" (json-markup (ly:event-property event 'text))
            "glyphs" (json-glyphs (ly:event-property event 'text))
            "dir" (json-number (ly:event-property event 'direction 0))))
     ((sustain-event engraver event)
      (emit (ly:translator-context engraver) event "sustain" "dir" (event-direction event)))
     ((una-corda-event engraver event)
      (emit (ly:translator-context engraver) event "una-corda" "dir" (event-direction event)))
     ((breathing-event engraver event)
      (emit (ly:translator-context engraver) event "breathe"))
     ((glissando-event engraver event)
      (emit (ly:translator-context engraver) event "glissando")))))

%% Staves: the context properties that change what the notes mean.

#(define (lilyport-staff-engraver context)
   (let ((clef #f) (key #f))
     (make-engraver
      ((process-music engraver)
       (let ((glyph (ly:context-property context 'clefGlyph #f))
             (position (ly:context-property context 'clefPosition 0))
             (transposition (ly:context-property context 'clefTransposition 0))
             (alterations (ly:context-property context 'keyAlterations '())))
         (if (not (equal? clef (list glyph position transposition)))
             (begin
               (set! clef (list glyph position transposition))
               (emit context #f "clef"
                     "glyph" (json-string (or glyph ""))
                     "position" (json-number position)
                     "transposition" (json-number transposition))))
         (if (not (equal? key alterations))
             (begin
               (set! key alterations)
               (emit context #f "key"
                     "tonic" (json-pitch (ly:context-property context 'tonic (ly:make-pitch 0 0 0)))
                     "alterations"
                     (string-append
                      "["
                      (string-join
                       (map (lambda (a)
                              (if (pair? (car a))
                                  ;; (octave . step) . alteration
                                  (format #f "[~a,~a]" (cdar a) (json-number (cdr a)))
                                  (format #f "[~a,~a]" (car a) (json-number (cdr a)))))
                            alterations)
                       ",")
                      "]")))))))))

%% The header. Engravers can't see it, so the book handler (which LilyPond
%% calls for each book, before translating its scores) queues the header
%% scopes of each score that will be engraved, innermost first; each Score
%% engraver takes the next. Scores without a \layout get no engraver, so they
%% get no place in the queue either.

#(define lilyport-pending-headers '())

#(define (lilyport-engraved-score? score)
   ;; A score without output definitions gets the default \layout. (Before
   ;; output-def-kind, if older LilyPonds lack it, every score counts.)
   (let ((defs (ly:score-output-defs score)))
     (or (null? defs)
         (any (lambda (def) (not (eq? (ly:output-def-lookup def 'output-def-kind #f) 'midi)))
              defs))))

#(define (lilyport-queue-headers book outer)
   (let ((scopes (if (module? (ly:book-header book))
                     (cons (ly:book-header book) outer)
                     outer)))
     ;; LilyPond keeps parts and scores newest first.
     (for-each (lambda (part) (lilyport-queue-headers part scopes))
               (reverse (ly:book-book-parts book)))
     (for-each
      (lambda (score)
        (if (lilyport-engraved-score? score)
            (set! lilyport-pending-headers
                  (append lilyport-pending-headers
                          (list (if (module? (ly:score-header score))
                                    (cons (ly:score-header score) scopes)
                                    scopes))))))
      (reverse (ly:book-scores book)))))

#(define (lilyport-wrap-book-handler handler)
   (lambda (book . rest)
     (lilyport-queue-headers book '())
     (apply handler book rest)))

#(set! toplevel-book-handler (lilyport-wrap-book-handler toplevel-book-handler))
#(if (defined? 'default-toplevel-book-handler)
     (set! default-toplevel-book-handler
           (lilyport-wrap-book-handler default-toplevel-book-handler)))

#(define (json-header scopes)
   "The fields of SCOPES (header modules, innermost first) as a JSON object,
an inner field hiding an outer one; markups as their text."
   (let ((fields (make-hash-table)))
     (for-each
      (lambda (scope)
        (module-for-each
         (lambda (name variable)
           (if (not (hashq-ref fields name))
               (hashq-set! fields name (variable-ref variable))))
         scope))
      scopes)
     (string-append
      "{"
      (string-join
       (map (lambda (entry)
              (string-append (json-symbol (car entry)) ":" (json-markup (cdr entry))))
            (sort (hash-map->list cons fields)
                  (lambda (a b) (string<? (symbol->string (car a))
                                          (symbol->string (car b))))))
       ",")
      "}")))

%% The score: time, tempo, bar lines and repeats, and the header.

#(define (lilyport-score-engraver context)
   (let ((time #f) (bar-type #f) (scopes #f))
     (make-engraver
      ((initialize engraver)
       (set! lilyport-score-number (1+ lilyport-score-number))
       (if (pair? lilyport-pending-headers)
           (begin
             (set! scopes (car lilyport-pending-headers))
             (set! lilyport-pending-headers (cdr lilyport-pending-headers)))))
      ((process-music engraver)
       (if scopes
           (begin
             (emit context #f "header" "fields" (json-header scopes))
             (set! scopes #f)))
       ;; timeSignature since 2.25 (timeSignatureFraction before, deprecated)
       (let ((fraction (or (ly:context-property context 'timeSignature #f)
                           (and (not (ly:version? >= '(2 25 0)))
                                (ly:context-property context 'timeSignatureFraction #f))))
             (which (ly:context-property context 'whichBar #f))
             (repeats (ly:context-property context 'repeatCommands '())))
         (if (and fraction (not (equal? time fraction)))
             (begin
               (set! time fraction)
               (emit context #f "time" "fraction" (json-fraction fraction))))
         (if (and (string? which) (not (string-null? which)))
             (emit context #f "bar-line" "type" (json-string which)))
         (if (pair? repeats)
             (emit context #f "repeat-commands"
                   "commands"
                   (json-string (format #f "~s" repeats))))))
      (listeners
       ((tempo-change-event engraver event)
        (let ((unit (ly:event-property event 'tempo-unit #f))
              (count (ly:event-property event 'metronome-count #f))
              (text (ly:event-property event 'text #f)))
          (apply emit context event "tempo"
                 (append
                  (if text (list "text" (json-markup text)) '())
                  (if unit (list "unit" (json-duration unit)) '())
                  (if (number? count) (list "count" (json-number count)) '())))))))))

\layout {
  \context { \Voice \consists #lilyport-voice-engraver }
  \context { \DrumVoice \consists #lilyport-voice-engraver }
  \context { \Staff \consists #lilyport-staff-engraver }
  \context { \Score \consists #lilyport-score-engraver }
}
