async function enviarPergunta() {
    const input = document.getElementById("pergunta-input");
    const chatBox = document.getElementById("chat-box");
    const loading = document.getElementById("loading-text");
    const pergunta = input.value.trim();

    if (!pergunta) return;

    // Adiciona a pergunta na tela
    chatBox.innerHTML += `<div class="mensagem-usuario">Você: ${pergunta}</div>`;
    input.value = ""; // limpa o input
    chatBox.scrollTop = chatBox.scrollHeight; // rola para baixo

    loading.style.display = "block"; // Mostra o "Pensando..."

    try {
        // Chamada para a nossa FastAPI
        const response = await fetch("/api/perguntar", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ pergunta: pergunta })
        });

        const data = await response.json();

        // Adiciona a resposta da IA na tela
        chatBox.innerHTML += `<div class="mensagem-ia"><strong>Auditor:</strong> ${data.resposta}</div>`;
    } catch (error) {
        chatBox.innerHTML += `<div class="mensagem-ia" style="color: red;"><strong>Erro:</strong> Falha ao conectar com o servidor.</div>`;
    } finally {
        loading.style.display = "none";
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}
async function enviarPDF() {
    const fileInput = document.getElementById("pdf-upload");
    const statusText = document.getElementById("upload-status");
    if (fileInput.files.length === 0) return;
    const formData = new FormData();
    formData.append("arquivo", fileInput.files[0]);

    statusText.style.color = "blue";
    statusText.innerText = "⏳ Lendo o PDF, fatiando textos e criando vetores... Aguarde.";

    try {
        const response = await fetch("/api/upload", {
            method: "POST",
            body: formData // Note que não usamos JSON.stringify aqui, usamos FormData para arquivos!
        });

        const data = await response.json();
        statusText.style.color = "green";
        statusText.innerText = "✅ " + data.mensagem;

    } catch (error) {
        statusText.style.color = "red";
        statusText.innerText = "❌ Erro ao enviar o arquivo.";
    }
}
