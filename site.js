/* myportfolioos.com — landing interactions.
 *
 * v1: the six answers already live in the HTML as <article class="qa-item">.
 * This file reads them, replaces the plain list with the card grid from the
 * design, and replays a card's answer into the transcript when it is clicked.
 *
 * PROGRESSIVE ENHANCEMENT IS THE POINT. With JavaScript off, the page is a
 * readable question-and-answer list and every answer is still in the markup for
 * a crawler. Nothing here invents content; it only moves content that is
 * already on the page.
 *
 * v2 changes one function. `answerFor(id)` returns stored HTML today; it becomes
 * a fetch to the model proxy. The transcript, reset, deep links, focus handling
 * and the no-JS fallback all stay exactly as they are.
 */
(function () {
  "use strict";

  var qa = document.getElementById("qa");
  var log = document.getElementById("log");
  var resetBtn = document.getElementById("reset");
  var transcript = document.getElementById("transcript");
  if (!qa || !log || !resetBtn) return;

  /* The untouched panel centres itself — removing the composer left ~350px of dead
     space under the cards. Centring stops the moment there is a conversation, because
     a centred flex column that overflows is clipped at the top, not scrollable to it. */
  function setEmpty(isEmpty) {
    if (!transcript) return;
    if (isEmpty) transcript.classList.add("is-empty");
    else transcript.classList.remove("is-empty");
  }
  setEmpty(true);

  var items = Array.prototype.slice.call(qa.querySelectorAll(".qa-item"));
  if (!items.length) return;

  // Lift the questions and answers out of the DOM before rebuilding the section.
  var questions = items.map(function (el) {
    var h = el.querySelector("h3");
    var a = el.querySelector(".answer");
    return {
      id: el.id,
      text: h ? h.textContent.trim() : "",
      html: a ? a.innerHTML.trim() : ""
    };
  }).filter(function (q) { return q.id && q.text && q.html; });

  if (!questions.length) return;

  var byId = {};
  questions.forEach(function (q) { byId[q.id] = q; });

  var asked = [];

  /* ------------------------------------------------------------ rendering */

  var heading = qa.querySelector(".kicker");
  qa.innerHTML = "";
  if (heading) qa.appendChild(heading);

  var grid = document.createElement("div");
  grid.className = "qa-grid";

  questions.forEach(function (q) {
    var b = document.createElement("button");
    b.type = "button";
    b.className = "ask";
    b.dataset.id = q.id;

    var label = document.createElement("span");
    label.textContent = q.text;

    var arrow = document.createElement("span");
    arrow.className = "arrow";
    arrow.setAttribute("aria-hidden", "true");
    arrow.textContent = "↗";

    b.appendChild(label);
    b.appendChild(arrow);
    b.addEventListener("click", function () { ask(q.id, { scroll: true, focus: true, animate: true }); });
    grid.appendChild(b);
  });

  qa.appendChild(grid);

  function cardFor(id) {
    return grid.querySelector('.ask[data-id="' + id + '"]');
  }

  function turn(role, who) {
    var wrap = document.createElement("div");
    wrap.className = "turn " + role;
    var label = document.createElement("p");
    label.className = "who";
    label.textContent = who;
    var body = document.createElement("div");
    body.className = "bubble";
    wrap.appendChild(label);
    wrap.appendChild(body);
    return { wrap: wrap, body: body };
  }

  /* ------------------------------------------------------------ the answer source
   * v2: replace the body of this function with a call to the model proxy and
   * return a promise. Everything downstream already treats it as async. */
  function answerFor(id) {
    var q = byId[id];
    return Promise.resolve(q ? q.html : "");
  }

  /* ------------------------------------------------------------ ask */

  /* `opts.scroll` and `opts.focus` are separate on purpose.
   *
   * A click should do both: the visitor acted, so move them to the answer and put
   * focus there for a screen reader. Arriving on /#q-decision should scroll but NOT
   * steal focus — taking focus on page load drops a screen-reader user into the
   * middle of the document with no context for how they got there.
   *
   * 2026-09-11: this was a single `moveFocus` flag and the deep-link path passed
   * false, which suppressed the scroll too. Once #log moved below the card grid that
   * left /#q-decision showing 56px of a 430px answer, sliced through the glyphs by
   * the composer. That link is the one Yehudi pastes to a recruiter. */
  function ask(id, opts) {
    opts = opts || {};
    var q = byId[id];
    if (!q || asked.indexOf(id) !== -1) return Promise.resolve(false);

    asked.push(id);
    setEmpty(false);

    var card = cardFor(id);
    if (card) {
      card.setAttribute("aria-disabled", "true");
      card.disabled = true;
    }

    var you = turn("you", "You");
    var p = document.createElement("p");
    p.style.margin = "0";
    p.textContent = q.text;
    you.body.appendChild(p);
    log.appendChild(you.wrap);

    return answerFor(id).then(function (html) {
      var ai = turn("ai", "Yehudi");
      ai.body.innerHTML = html;
      log.appendChild(ai.wrap);

      resetBtn.hidden = false;

      // Shareable: /#q-decision opens straight into that answer.
      if (window.history && window.history.replaceState) {
        window.history.replaceState(null, "", "#" + id);
      }

      if (opts.focus) {
        ai.wrap.setAttribute("tabindex", "-1");
        ai.wrap.focus({ preventScroll: true });
      }
      if (opts.scroll) scrollTranscriptTo(ai.wrap, opts.animate);
      return true;
    });
  }

  /* ------------------------------------------------------------ reset */

  function reset() {
    log.innerHTML = "";
    asked = [];
    Array.prototype.forEach.call(grid.querySelectorAll(".ask"), function (b) {
      b.removeAttribute("aria-disabled");
      b.disabled = false;
    });
    resetBtn.hidden = true;
    setEmpty(true);
    if (window.history && window.history.replaceState) {
      window.history.replaceState(null, "", window.location.pathname);
    }
    var first = grid.querySelector(".ask");
    if (first) first.focus();
  }

  resetBtn.addEventListener("click", reset);

  /* scrollIntoView() scrolls EVERY scrollable ancestor, the document included. On
   * /#q-decision that pushed the header off the top and pulled the Portfolio OS
   * section into view — the visitor landed on a page that looked mid-scroll and had
   * lost its own masthead. Move only the transcript's own scrollTop. */
  function scrollTranscriptTo(el, animate) {
    var tr = document.getElementById("transcript");
    if (!tr) return;
    var top = tr.scrollTop + (el.getBoundingClientRect().top - tr.getBoundingClientRect().top) - 8;
    top = Math.max(0, Math.min(top, tr.scrollHeight - tr.clientHeight));
    var smooth = animate && !prefersReducedMotion();
    if (smooth && tr.scrollTo) {
      tr.scrollTo({ top: top, behavior: "smooth" });
    } else {
      tr.scrollTop = top;   // assignment always applies; scrollTo+smooth can be dropped
    }
  }

  function prefersReducedMotion() {
    return window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  }

  /* ------------------------------------------------------------ deep link */

  function openFromHash() {
    var id = (window.location.hash || "").replace(/^#/, "");
    if (id && byId[id] && asked.indexOf(id) === -1) {
      // No animation on arrival. Someone who followed /#q-decision asked to BE at that
      // answer, not to watch a scroll from the top — and a smooth scroll can be dropped
      // entirely if the browser is still settling, leaving them at the top with no clue.
      ask(id, { scroll: true, focus: false, animate: false });
    }
  }

  openFromHash();
  window.addEventListener("hashchange", openFromHash);

  /* ------------------------------------------------------------ scroll cue */

  /* #portfolio-os is not a question id, so openFromHash ignores it and the browser's
     native anchor jump does the work. Nothing to wire up. */

  /* ------------------------------------------------------------ test surface */

  window.__site = {
    ask: ask,
    reset: reset,
    questions: questions,
    asked: function () { return asked.slice(); }
  };
})();
