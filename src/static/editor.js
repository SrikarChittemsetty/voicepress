/**
 * Post body editor: live Markdown preview + browser speech dictation.
 *
 * Future: a paid or API-based transcription flow can add another button here
 * and call a backend route — see attachApiTranscriptionPlaceholder() below.
 */
(function (global) {
  "use strict";

  /**
   * Reserved for later: wire a button to POST audio to your server and paste returned text.
   * Not used in this project step (no API keys, no backend route).
   */
  function attachApiTranscriptionPlaceholder() {
    // Example later: document.getElementById("api-transcribe").addEventListener("click", …);
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  function inlineMarkdown(text) {
    let html = text;
    html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    html = html.replace(/\*(.+?)\*/g, "<em>$1</em>");
    return html;
  }

  function renderMarkdownPreview(bodyTextarea, previewElement) {
    const raw = bodyTextarea.value || "";
    const lines = raw.split("\n");
    const htmlParts = [];
    let listItems = [];

    function flushList() {
      if (listItems.length > 0) {
        htmlParts.push("<ul>" + listItems.join("") + "</ul>");
        listItems = [];
      }
    }

    for (let i = 0; i < lines.length; i++) {
      const safeLine = escapeHtml(lines[i].trim());
      if (safeLine.startsWith("- ")) {
        listItems.push("<li>" + inlineMarkdown(safeLine.slice(2)) + "</li>");
        continue;
      }

      flushList();

      if (!safeLine) {
        htmlParts.push("<br>");
        continue;
      }

      if (safeLine.startsWith("# ")) {
        htmlParts.push("<h1>" + inlineMarkdown(safeLine.slice(2)) + "</h1>");
      } else {
        htmlParts.push("<p>" + inlineMarkdown(safeLine) + "</p>");
      }
    }

    flushList();
    previewElement.innerHTML = htmlParts.join("");
  }

  function insertTextAtCursor(textarea, text) {
    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const before = textarea.value.substring(0, start);
    const after = textarea.value.substring(end);
    const needsSpace =
      before.length > 0 && !/\s$/.test(before) && text.length > 0 && !/^\s/.test(text);
    const insert = (needsSpace ? " " : "") + text;
    textarea.value = before + insert + after;
    const pos = start + insert.length;
    textarea.selectionStart = pos;
    textarea.selectionEnd = pos;
    textarea.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function isBrowserDictationSupported() {
    return !!(global.SpeechRecognition || global.webkitSpeechRecognition);
  }

  function friendlySpeechErrorMessage(errorCode) {
    if (errorCode === "not-allowed") {
      return "Microphone access was denied. Allow the microphone for this site in your browser settings, then try again.";
    }
    if (errorCode === "no-speech") {
      return "No speech was detected. Try again and speak clearly.";
    }
    if (errorCode === "audio-capture") {
      return "No microphone was found. Check that a microphone is connected.";
    }
    if (errorCode === "network") {
      return "Speech recognition had a network error. Check your connection and try again.";
    }
    return "Dictation stopped (" + errorCode + "). You can edit the text by hand.";
  }

  function attachBrowserDictation(bodyTextarea, onTextChanged, statusEl, startBtn, stopBtn) {
    if (!isBrowserDictationSupported()) {
      statusEl.textContent = "Voice dictation is not supported in this browser.";
      startBtn.disabled = true;
      stopBtn.disabled = true;
      return;
    }

    const SpeechRecognition = global.SpeechRecognition || global.webkitSpeechRecognition;
    let recognition = null;
    let listening = false;
    let closedBecauseOfSpeechError = false;

    function updateDictationButtons(listeningNow) {
      listening = listeningNow;
      startBtn.disabled = listeningNow;
      stopBtn.disabled = !listeningNow;
    }

    function startRecognition() {
      if (listening) {
        return;
      }
      closedBecauseOfSpeechError = false;
      recognition = new SpeechRecognition();
      recognition.lang = (document.documentElement.lang || "en-US").replace("_", "-");
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onstart = function () {
        updateDictationButtons(true);
        statusEl.textContent = "Listening… speak clearly. Click Stop when you are done.";
      };

      recognition.onresult = function (event) {
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const piece = event.results[i];
          if (piece.isFinal) {
            const transcript = piece[0].transcript;
            if (transcript) {
              insertTextAtCursor(bodyTextarea, transcript);
              onTextChanged();
            }
          }
        }
      };

      recognition.onerror = function (event) {
        closedBecauseOfSpeechError = true;
        statusEl.textContent = friendlySpeechErrorMessage(event.error);
        updateDictationButtons(false);
      };

      recognition.onend = function () {
        updateDictationButtons(false);
        if (!closedBecauseOfSpeechError) {
          statusEl.textContent = "Dictation stopped.";
        }
        closedBecauseOfSpeechError = false;
      };

      try {
        recognition.start();
      } catch (err) {
        statusEl.textContent = "Could not start dictation. Try again or refresh the page.";
        updateDictationButtons(false);
      }
    }

    function stopRecognition() {
      if (recognition && listening) {
        try {
          recognition.stop();
        } catch (e) {
          /* ignore */
        }
      } else {
        updateDictationButtons(false);
        statusEl.textContent = "Dictation stopped.";
      }
    }

    startBtn.addEventListener("click", startRecognition);
    stopBtn.addEventListener("click", stopRecognition);

    statusEl.textContent = "Ready. Click Start dictation to use your microphone (free, in-browser).";
    attachApiTranscriptionPlaceholder();
  }

  function initPostBodyEditor() {
    const bodyTextarea = document.getElementById("body");
    const previewEl = document.getElementById("markdown-preview-content");
    const statusEl = document.getElementById("dictation-status");
    const startBtn = document.getElementById("dictation-start");
    const stopBtn = document.getElementById("dictation-stop");

    if (!bodyTextarea || !previewEl || !statusEl || !startBtn || !stopBtn) {
      return;
    }

    function refreshPreview() {
      renderMarkdownPreview(bodyTextarea, previewEl);
    }

    bodyTextarea.addEventListener("input", refreshPreview);
    refreshPreview();

    attachBrowserDictation(bodyTextarea, refreshPreview, statusEl, startBtn, stopBtn);
  }

  global.PostBodyEditor = {
    init: initPostBodyEditor,
    attachApiTranscriptionPlaceholder: attachApiTranscriptionPlaceholder,
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPostBodyEditor);
  } else {
    initPostBodyEditor();
  }
})(typeof window !== "undefined" ? window : this);
