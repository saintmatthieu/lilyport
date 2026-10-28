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
%% "playback" gives the tempo LilyPond's MIDI starts at (wholes_per_minute):
%% the score's \midi's, else that of a score of the book with only a \midi
%% (Mutopia's \unfoldRepeats twin); "default": true if it is LilyPond's
%% default (no \tempo in the \midi).
%%
%% Repeats: "repeat" (dir -1 a start, 1 an end; "count" the times played
%% from a start, or gone back from an end), "volta" (dir -1 a bracket's start,
%% with its "numbers" from \alternative or its "text" set by hand; 1 its end).
%%
%% Each staff announces itself once (kind "staff": its name, the context it
%% is in, e.g. a PianoStaff, its order of creation, and its instrument name),
%% and so does each Dynamics line ("dynamics": true), whose events carry its
%% id as their staff. "timing" records
%% \cadenzaOn/Off (on: false/true).
%%
%% A note's "stem" is the direction its context sets (1 up, -1 down), absent
%% when LilyPond chooses. Notes and rests drawn invisibly (\hideNotes, \omit)
%% have "visible": false.
%%
%% A note inside a chord carries its own tie ("tie": true), \repeatTie
%% ("repeat_tie": true) and fingerings ("fingers"), which LilyPond doesn't
%% broadcast as events.
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
          ((markup? m) (markup->string (lilyport-note-text m)))
          (else (format #f "~a" m)))))

#(define lilyport-accidental-markups
   `((,flat-markup . "accidentals.flat") (,sharp-markup . "accidentals.sharp")
     (,natural-markup . "accidentals.natural") (,doubleflat-markup . "accidentals.flatflat")
     (,doublesharp-markup . "accidentals.doublesharp")))

#(define (markup-glyphs m)
   "The music glyphs a markup draws (\\musicglyph, \\flat...), in order:
text that stands for a mark, such as a \"Ped.\" drawn as text rather than
with \\sustainOn, or a turn with the accidentals of its notes."
   (cond
    ((and (pair? m) (eq? (car m) musicglyph-markup) (pair? (cdr m)) (string? (cadr m)))
     (list (cadr m)))
    ((and (pair? m) (assq (car m) lilyport-accidental-markups))
     (list (cdr (assq (car m) lilyport-accidental-markups))))
    ((pair? m) (append-map markup-glyphs m))
    (else '())))

#(define lilyport-note-symbols #("𝅝" "𝅗𝅥" "♩" "♪" "𝅘𝅥𝅯" "𝅘𝅥𝅰"))

#(define (lilyport-note-text m)
   "M with its \\note markups as note symbols, which markup->string drops."
   (define (symbol log dots)
     (string-append (if (and (>= log 0) (< log (vector-length lilyport-note-symbols)))
                        (vector-ref lilyport-note-symbols log)
                        "♩")
                    (make-string dots #\.)))
   (cond
    ((and (pair? m) (eq? (car m) note-markup) (pair? (cdr m)))
     (let ((duration (cadr m)))
       (if (ly:duration? duration)
           (symbol (ly:duration-log duration) (ly:duration-dot-count duration))
           "♩")))
    ((and (pair? m) (eq? (car m) note-by-number-markup) (pair? (cdr m)))
     (symbol (cadr m) (caddr m)))
    ((pair? m) (cons (lilyport-note-text (car m)) (lilyport-note-text (cdr m))))
    (else m)))

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
             ;; a Dynamics line between staves stands for a staff
             (lilyport-context-id (or (ly:context-find ctx 'Staff)
                                      (ly:context-find ctx 'Dynamics)))
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
      ;; The tie and fingerings of a note inside a chord (<c~ e-3>), which
      ;; LilyPond doesn't broadcast (a lone note's arrive as events instead).
      (let* ((ctx (ly:translator-context engraver))
             (pitch (ly:event-property event 'pitch #f))
             (articulations (ly:event-property event 'articulations '()))
             (tied (any (lambda (a) (memq 'tie-event (ly:event-property a 'class)))
                        articulations))
             (repeat-tied (any (lambda (a) (memq 'repeat-tie-event (ly:event-property a 'class)))
                               articulations))
             (fingers (filter-map
                       (lambda (a)
                         (and (memq 'fingering-event (ly:event-property a 'class))
                              (json-number (ly:event-property a 'digit 0))))
                       articulations))
             ;; \voiceOne, \stemUp...: 1 up, -1 down; none if LilyPond decides
             (stem (assq-ref (ly:context-grob-definition ctx 'Stem) 'direction)))
        (apply emit ctx event "note"
               (append
                (if pitch (list "pitch" (json-pitch pitch)) '())
                (if (and (number? stem) (not (zero? stem)))
                    (list "stem" (json-number stem))
                    '())
                (list "duration" (json-duration (ly:event-property event 'duration)))
                (if tied (list "tie" "true") '())
                (if repeat-tied (list "repeat_tie" "true") '())
                (if (lilyport-hidden? ctx 'NoteHead) (list "visible" "false") '())
                (if (pair? fingers)
                    (list "fingers" (string-append "[" (string-join fingers ",") "]"))
                    '())))))
     ((rest-event engraver event)
      (let ((ctx (ly:translator-context engraver)))
        (apply emit ctx event "rest"
               "duration" (json-duration (ly:event-property event 'duration))
               (if (lilyport-hidden? ctx 'Rest) (list "visible" "false") '()))))
     ((multi-measure-rest-event engraver event)
      (emit (ly:translator-context engraver) event "multi-measure-rest"
            "duration" (json-duration (ly:event-property event 'duration))))
     ((skip-event engraver event)
      (emit (ly:translator-context engraver) event "skip"
            "duration" (json-duration (ly:event-property event 'duration))))
     ((tie-event engraver event)
      (emit (ly:translator-context engraver) event "tie"))
     ;; \repeatTie: tied from the end of the repeated music (a second ending)
     ((repeat-tie-event engraver event)
      (emit (ly:translator-context engraver) event "repeat-tie"))
     ((tuplet-span-event engraver event)
      (emit (ly:translator-context engraver) event "tuplet"
            "dir" (event-direction event)))
     ((slur-event engraver event)
      (emit (ly:translator-context engraver) event "slur" "dir" (event-direction event)))
     ((ottava-event engraver event)
      ;; \ottava #1: 8va (notes drawn an octave lower), #0 ends it
      (emit (ly:translator-context engraver) event "ottava"
            "octaves" (json-number (ly:event-property event 'ottava-number 0))))
     ((trill-span-event engraver event)
      (emit (ly:translator-context engraver) event "trill-span" "dir" (event-direction event)))
     ((phrasing-slur-event engraver event)
      (emit (ly:translator-context engraver) event "phrasing-slur" "dir" (event-direction event)))
     ((articulation-event engraver event)
      (emit (ly:translator-context engraver) event "articulation"
            "type" (json-symbol (ly:event-property event 'articulation-type))))
     ((fingering-event engraver event)
      (emit (ly:translator-context engraver) event "fingering"
            "digit" (json-number (ly:event-property event 'digit 0))))
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

%% Beams, as LilyPond made them (by hand or automatically): one record per
%% beam when its voice ends, with the times of its stems. Importers that get
%% no beams make their own, with stems in their default directions.

#(define (lilyport-beam-engraver context)
   (let ((beams '()))
     (make-engraver
      (acknowledgers
       ((beam-interface engraver grob source-engraver)
        (set! beams (cons grob beams))))
      ((finalize engraver)
       (for-each
        (lambda (beam)
          (let ((stems (ly:grob-array->list (ly:grob-object beam 'stems))))
            (if (pair? stems)
                (emit context #f "beam"
                      "stems" (string-append
                               "["
                               (string-join (map (lambda (stem) (json-moment (grob::when stem)))
                                                 stems)
                                            ",")
                               "]")))))
        (reverse beams))))))

%% Staves: the context properties that change what the notes mean.

#(define lilyport-context-order 0)

#(define (lilyport-next-order)
   (set! lilyport-context-order (1+ lilyport-context-order))
   lilyport-context-order)

#(define (lilyport-announce context order)
   "Which staves make one instrument (a PianoStaff's), in which order (the
Dynamics lines between them too, which belong to a staff), and its name."
   (let ((parent (ly:context-parent context))
         (instrument (ly:context-property context 'instrumentName #f)))
     (apply emit context #f "staff"
            "name" (json-string (ly:context-id context))
            "parent" (json-symbol (ly:context-name parent))
            "parent_id" (json-number (lilyport-context-id parent))
            "order" (json-number order)
            (append
             (if (eq? (ly:context-name context) 'Dynamics) (list "dynamics" "true") '())
             (if instrument (list "instrument" (json-markup instrument)) '())))))

%% A Dynamics line (\new Dynamics, between or under staves): its dynamics,
%% hairpins and pedals go to the voice engraver; it announces itself.

#(define (lilyport-dynamics-engraver context)
   (let ((order #f) (announced #f))
     (make-engraver
      ((initialize engraver)
       (set! order (lilyport-next-order)))
      ((process-music engraver)
       (if (not announced)
           (begin
             (set! announced #t)
             (lilyport-announce context order)))))))

#(define (lilyport-staff-engraver context)
   (let ((clef #f) (key #f) (order #f) (announced #f))
     (make-engraver
      ((initialize engraver)
       (set! order (lilyport-next-order)))
      ((process-music engraver)
       (if (not announced)
           (begin
             (set! announced #t)
             (lilyport-announce context order)))
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
%% scopes of each score that will be engraved, innermost first, with the
%% tempo its MIDI starts at; each Score engraver takes the next. Scores without a \layout get no engraver, so they
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
     (let* ((scores (reverse (ly:book-scores book)))
            (midi-only (remove lilyport-engraved-score? scores)))
       (for-each
        (lambda (score)
          (if (lilyport-engraved-score? score)
              (set! lilyport-pending-headers
                    (append lilyport-pending-headers
                            (list (cons (if (module? (ly:score-header score))
                                            (cons (ly:score-header score) scopes)
                                            scopes)
                                        (lilyport-midi-tempo
                                         (if (pair? (lilyport-midi-defs score))
                                             score
                                             (lilyport-midi-twin score scores midi-only)))))))))
        scores))))

#(define (lilyport-midi-defs score)
   (filter (lambda (def) (eq? (ly:output-def-lookup def 'output-def-kind #f) 'midi))
           (ly:score-output-defs score)))

#(define (lilyport-midi-twin score scores midi-only)
   "The score with only a \\midi that plays SCORE: the next one after it in
the book, else the last before it; else SCORE."
   (let* ((after (cdr (memq score scores)))
          (next (find (lambda (s) (memq s midi-only)) after))
          (before (filter (lambda (s) (not (memq s (memq score scores)))) midi-only)))
     (or next (and (pair? before) (last before)) score)))

#(define (lilyport-midi-tempo score)
   "The tempo (wholes per minute) LilyPond's MIDI of SCORE starts at, and
whether it is the default (4 = 60, the \\midi says none), as a pair: its
\\midi block's, else the default \\midi's."
   (let* ((midis (lilyport-midi-defs score))
          (midi (if (pair? midis) (car midis) (ly:parser-lookup '$defaultmidi)))
          (score-def (and (ly:output-def? midi) (ly:output-def-lookup midi 'Score #f)))
          ;; Newest first: \midi { \tempo ... } before the default's.
          (ops (if score-def
                   (filter (lambda (op) (and (eq? (car op) 'assign)
                                             (eq? (cadr op) 'tempoWholesPerMinute)))
                           (ly:context-def-lookup score-def 'property-ops '()))
                   '()))
          (tempo (and (pair? ops) (caddr (car ops)))))
     (cons (if (ly:moment? tempo) (ly:moment-main tempo) tempo)
           (< (length ops) 2))))

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

#(define (lilyport-hidden? context grob)
   "Whether the context's settings hide GROB (\\omit, \\hide, transparent)."
   (let ((definition (ly:context-grob-definition context grob)))
     (or (eq? (assq-ref definition 'transparent) #t)
         (let ((stencil (assq 'stencil definition)))
           (and stencil (not (cdr stencil)))))))

%% The score: time, tempo, bar lines and repeats, and the header.

#(define (lilyport-score-engraver context)
   (let ((time #f) (bar-type #f) (scopes #f) (midi-tempo #f) (timing #t)
         (volta-moment #f) (voltas-seen '()))
     (make-engraver
      ((initialize engraver)
       (set! lilyport-score-number (1+ lilyport-score-number))
       (if (pair? lilyport-pending-headers)
           (begin
             (set! scopes (caar lilyport-pending-headers))
             (set! midi-tempo (cdar lilyport-pending-headers))
             (set! lilyport-pending-headers (cdr lilyport-pending-headers)))))
      ((process-music engraver)
       (if scopes
           (begin
             (emit context #f "header" "fields" (json-header scopes))
             (if (and midi-tempo (car midi-tempo))
                 (apply emit context #f "playback"
                        "wholes_per_minute" (json-number (car midi-tempo))
                        (if (cdr midi-tempo) (list "default" "true") '())))
             (set! scopes #f)))
       ;; timeSignature since 2.25 (timeSignatureFraction before, deprecated)
       (let ((fraction (or (ly:context-property context 'timeSignature #f)
                           (and (not (ly:version? >= '(2 25 0)))
                                (ly:context-property context 'timeSignatureFraction #f))))
             (which (ly:context-property context 'whichBar #f))
             (repeats (ly:context-property context 'repeatCommands '()))
             (now-timing (ly:context-property context 'timing #t)))
         ;; Off in a cadenza (\cadenzaOn), where the bar position stays put.
         (if (not (eq? timing now-timing))
             (begin
               (set! timing now-timing)
               (emit context #f "timing" "on" (if now-timing "true" "false"))))
         (if (and fraction (not (equal? time fraction)))
             (begin
               (set! time fraction)
               ;; style C draws 4/4 and 2/2 as C and cut C
               (emit context #f "time" "fraction" (json-fraction fraction)
                     "style" (json-symbol
                              (assq-ref (ly:context-grob-definition context 'TimeSignature)
                                        'style)))))
         (if (and (string? which) (not (string-null? which)))
             (emit context #f "bar-line" "type" (json-string which)))
         ;; Set by \repeat volta (start and end), or by hand (voltas too).
         (for-each
          (lambda (command)
            (let ((name (if (pair? command) (car command) command))
                  (args (if (pair? command) (cdr command) '())))
              (case name
                ((start-repeat end-repeat)
                 (apply emit context #f "repeat" "dir" (if (eq? name 'start-repeat) "-1" "1")
                        (if (and (pair? args) (integer? (car args)))
                            (list "count" (json-number (car args)))
                            '())))
                ((volta)
                 (if (and (pair? args) (car args))
                     (emit context #f "volta" "dir" "-1" "text" (json-markup (car args)))
                     (emit context #f "volta" "dir" "1")))
                (else (emit context #f "repeat-command" "name" (json-symbol name))))))
          (if (list? repeats) repeats '()))))
      (listeners
       ;; \alternative's brackets; each staff sends its copy, recorded once.
       ((volta-span-event engraver event)
        (let ((dir (ly:event-property event 'span-direction))
              (numbers (ly:event-property event 'volta-numbers '()))
              (now (json-moment (ly:context-current-moment context))))
          (if (not (equal? now volta-moment))
              (begin (set! volta-moment now) (set! voltas-seen '())))
          (if (not (member (cons dir numbers) voltas-seen))
              (begin
                (set! voltas-seen (cons (cons dir numbers) voltas-seen))
                (emit context event "volta" "dir" (json-number dir)
                      "numbers" (string-append
                                 "[" (string-join (map json-number numbers) ",") "]"))))))
       ((tempo-change-event engraver event)
        (let ((unit (ly:event-property event 'tempo-unit #f))
              (count (ly:event-property event 'metronome-count #f))
              (text (ly:event-property event 'text #f)))
          (apply emit context event "tempo"
                 (append
                  ;; Hidden (Mutopia's Nocturne writes its own as text).
                  (if (lilyport-hidden? context 'MetronomeMark) (list "visible" "false") '())
                  (if text (list "text" (json-markup text)) '())
                  (if unit (list "unit" (json-duration unit)) '())
                  (if (number? count) (list "count" (json-number count)) '())))))))))

\layout {
  \context { \Voice \consists #lilyport-voice-engraver
                     \consists #lilyport-beam-engraver }
  \context { \DrumVoice \consists #lilyport-voice-engraver }
  \context { \Staff \consists #lilyport-staff-engraver }
  \context { \Dynamics \consists #lilyport-voice-engraver
                        \consists #lilyport-dynamics-engraver }
  \context { \Score \consists #lilyport-score-engraver }
}
