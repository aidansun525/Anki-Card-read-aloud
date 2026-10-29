// Card Read Aloud: pulls the visible text out of the review card and hands it
// to Anki's text-to-speech. Hidden things (hint fields, scripts, images,
// replay buttons) are skipped because we only walk what is actually shown.
(function () {
    "use strict";

    var SKIP_TAGS = {
        SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEMPLATE: 1, IMG: 1, SVG: 1,
        PICTURE: 1, VIDEO: 1, AUDIO: 1, IFRAME: 1, OBJECT: 1, CANVAS: 1,
        BUTTON: 1, INPUT: 1, TEXTAREA: 1, SELECT: 1, MATH: 1,
    };
    var SKIP_CLASSES = ["replay-button", "soundLink", "hint", "hints"];

    function skipped(el) {
        if (SKIP_TAGS[el.tagName.toUpperCase()]) return true;
        for (var i = 0; i < SKIP_CLASSES.length; i++) {
            if (el.classList.contains(SKIP_CLASSES[i])) return true;
        }
        // timers and other corner widgets some templates float over the card
        var name = ((el.id || "") + " " + (typeof el.className === "string" ? el.className : "")).toLowerCase();
        if (/timer|clock|countdown|stopwatch/.test(name)) return true;
        var cs = window.getComputedStyle(el);
        if (cs.position === "fixed" || cs.position === "sticky") return true;
        if (cs.color === "transparent" || /rgba\([^)]*,\s*0\)$/.test(cs.color)) return true;
        return cs.display === "none" || cs.visibility === "hidden" || cs.visibility === "collapse";
    }

    function isBlock(el) {
        if (el.tagName === "BR" || el.tagName === "HR") return true;
        var d = window.getComputedStyle(el).display;
        return d !== "inline" && d !== "inline-block" && d !== "contents";
    }

    function isExtra(el) {
        var id = (el.id || "").toLowerCase();
        return id === "extra" || el.classList.contains("extra");
    }

    // Collect text pieces, each marked with where it sits on the card.
    function collect(root) {
        var parts = [];
        var state = { afterHr: false, hasHr: false, clozeCount: 0 };

        function walk(node, cloze, extra) {
            if (node.nodeType === 3) {
                if (node.nodeValue) {
                    parts.push({ t: node.nodeValue, cloze: cloze, extra: extra, after: state.afterHr });
                }
                return;
            }
            if (node.nodeType !== 1) return;
            var el = node;
            if (el.tagName === "HR" && el.id === "answer") {
                state.afterHr = true;
                state.hasHr = true;
                parts.push({ t: "\n", cloze: -1, extra: extra, after: true });
                return;
            }
            if (skipped(el)) return;
            if (el.classList.contains("cloze") && cloze < 0) {
                cloze = state.clozeCount++;
            }
            extra = extra || isExtra(el);
            var block = isBlock(el);
            if (block) parts.push({ t: "\n", cloze: -1, extra: extra, after: state.afterHr });
            for (var c = el.firstChild; c; c = c.nextSibling) walk(c, cloze, extra);
            if (block) parts.push({ t: "\n", cloze: -1, extra: extra, after: state.afterHr });
        }

        for (var c = root.firstChild; c; c = c.nextSibling) walk(c, -1, false);
        return { parts: parts, hasHr: state.hasHr, clozeCount: state.clozeCount };
    }

    function join(parts) {
        return parts.map(function (p) { return p.t; }).join("");
    }

    // Front of a cloze: "[...]" becomes "blank", "[hint]" becomes "blank, hint".
    function frontText(info, opts) {
        var out = [];
        var lastCloze = -1;
        info.parts.forEach(function (p) {
            if (p.cloze >= 0) {
                if (p.cloze === lastCloze) return;
                lastCloze = p.cloze;
                var whole = join(info.parts.filter(function (q) { return q.cloze === p.cloze; })).trim();
                var m = /^\[(.*)\]$/.exec(whole);
                if (m) {
                    var hint = m[1].trim();
                    whole = hint && hint !== "..." && hint !== "…"
                        ? " " + opts.blank + ", hint: " + hint + ", "
                        : " " + opts.blank + " ";
                }
                out.push(whole);
            } else {
                lastCloze = -1;
                out.push(p.t);
            }
        });
        return out.join("");
    }

    function backText(info, opts) {
        var parts = info.parts;
        var keep = function (p) { return opts.readExtra || !p.extra; };
        if (info.clozeCount > 0) {
            if (opts.clozeBack === "sentence") {
                // the whole card minus anything after the answer line that isn't wanted
                return join(parts.filter(function (p) {
                    return keep(p) && (!p.after || opts.readExtra);
                }));
            }
            var answers = [];
            for (var i = 0; i < info.clozeCount; i++) {
                var a = join(parts.filter(function (p) { return p.cloze === i; })).trim();
                if (a) answers.push(a);
            }
            var text = answers.join(".\n");
            if (opts.readExtra) {
                var extra = join(parts.filter(function (p) { return p.cloze < 0 && (p.extra || p.after); }));
                if (extra.trim()) text += ".\n" + extra;
            }
            return text;
        }
        if (info.hasHr) {
            return join(parts.filter(function (p) { return p.after && keep(p); }));
        }
        return join(parts.filter(keep));
    }

    window.cardReadAloud = function (side, token, opts) {
        try {
            var root = document.getElementById("qa");
            if (!root) return;
            var info = collect(root);
            var text = side === "q" ? frontText(info, opts) : backText(info, opts);
            pycmd("readaloud:" + JSON.stringify({ side: side, token: token, text: text }));
        } catch (e) {
            console.log("Card Read Aloud: " + e);
        }
    };
})();
