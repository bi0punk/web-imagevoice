async function postOCR(file, lang) {
  const fd = new FormData();
  fd.append("image", file);
  fd.append("lang", lang);

  const res = await fetch("/api/ocr", { method: "POST", body: fd });
  const data = await res.json();
  if (!res.ok || !data.ok) throw new Error(data.error || "OCR falló");
  return data.text || "";
}

async function postTTS(payload) {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.error || "TTS falló");
  }
  return await res.blob(); // audio/mpeg
}

function setStatus(el, msg, kind) {
  el.textContent = msg || "";
  el.className = kind === "error" ? "error" : (kind === "ok" ? "ok" : "muted");
}

document.getElementById("btnOcr").addEventListener("click", async () => {
  const file = document.getElementById("image").files[0];
  const lang = document.getElementById("ocrLang").value;
  const status = document.getElementById("ocrStatus");
  if (!file) return setStatus(status, "Selecciona una imagen.", "error");

  setStatus(status, "Procesando OCR...", "");
  try {
    const text = await postOCR(file, lang);
    document.getElementById("text").value = text;
    setStatus(status, "OK", "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  }
});

document.getElementById("btnTts").addEventListener("click", async () => {
  const status = document.getElementById("ttsStatus");
  const text = document.getElementById("text").value || "";
  const voice = document.getElementById("voice").value || "";
  const rate = document.getElementById("rate").value || "+0%";
  const volume = document.getElementById("volume").value || "+0%";

  if (!text.trim()) return setStatus(status, "No hay texto para leer.", "error");

  setStatus(status, "Generando audio...", "");
  try {
    const blob = await postTTS({ text, voice, rate, volume });
    const url = URL.createObjectURL(blob);

    const player = document.getElementById("player");
    player.src = url;
    player.style.display = "block";
    player.play().catch(() => {});

    const dl = document.getElementById("download");
    dl.href = url;
    dl.style.display = "inline-block";

    setStatus(status, "OK", "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  }
});
