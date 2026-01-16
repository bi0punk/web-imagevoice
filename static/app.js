async function postOCRFile(file, lang) {
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

function showPreview(file) {
  const preview = document.getElementById("preview");
  const img = document.getElementById("previewImg");
  if (!preview || !img) return;

  const url = URL.createObjectURL(file);
  img.src = url;
  preview.style.display = "block";
}

async function doOCRFromFile(file) {
  const status = document.getElementById("ocrStatus");
  const lang = document.getElementById("ocrLang").value;

  setStatus(status, "Procesando OCR...", "");
  try {
    showPreview(file);
    const text = await postOCRFile(file, lang);
    document.getElementById("text").value = text;
    setStatus(status, "OK", "ok");
  } catch (e) {
    setStatus(status, e.message, "error");
  }
}

// --- Botón OCR (modo clásico con file input) ---
document.getElementById("btnOcr").addEventListener("click", async () => {
  const file = document.getElementById("image").files[0];
  const status = document.getElementById("ocrStatus");
  if (!file) return setStatus(status, "Selecciona una imagen.", "error");
  await doOCRFromFile(file);
});

// --- Drag & Drop + Paste ---
(function initDropAndPaste() {
  const dropzone = document.getElementById("dropzone");
  if (!dropzone) return;

  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("dragover");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("dragover");
  });

  dropzone.addEventListener("drop", async (e) => {
    e.preventDefault();
    dropzone.classList.remove("dragover");

    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      setStatus(document.getElementById("ocrStatus"), "El archivo no es una imagen.", "error");
      return;
    }

    // opcional: setear también el input file para que quede visible seleccionado
    try { document.getElementById("image").files = e.dataTransfer.files; } catch (_) {}

    await doOCRFromFile(file);
  });

  document.addEventListener("paste", async (e) => {
    const status = document.getElementById("ocrStatus");
    const items = e.clipboardData && e.clipboardData.items ? [...e.clipboardData.items] : [];
    const imgItem = items.find(i => i.type && i.type.startsWith("image/"));

    if (!imgItem) return; // no hay imagen pegada

    const file = imgItem.getAsFile();
    if (!file) return setStatus(status, "No pude leer la imagen del portapapeles.", "error");

    await doOCRFromFile(file);
  });
})();

// --- Botón TTS ---
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
