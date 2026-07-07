// Renderização própria dos diagramas Mermaid — ver comentário em mkdocs.yml sobre
// por que não usamos a integração automática do Material (falha silenciosa).
document.addEventListener("DOMContentLoaded", function () {
    if (typeof mermaid === "undefined") return;

    mermaid.initialize({
        startOnLoad: false,
        theme: "dark",
        themeVariables: {
            darkMode: true,
            background: "#101010",
            primaryColor: "#1a1a1a",
            primaryTextColor: "#f2f2f2",
            primaryBorderColor: "#00d992",
            lineColor: "#8b949e",
            secondaryColor: "#1a1a1a",
            tertiaryColor: "#0d0d0d",
        },
    });

    document.querySelectorAll("pre.mermaid-diagram > code").forEach(function (code, i) {
        var source = code.textContent;
        var container = document.createElement("div");
        container.className = "mermaid-diagram-rendered";

        mermaid.render("mermaid-diagram-" + i, source).then(function (result) {
            container.innerHTML = result.svg;
            code.closest("pre").replaceWith(container);
        }).catch(function (error) {
            console.error("[mermaid-init] Falha ao renderizar diagrama " + i, error);
        });
    });
});
