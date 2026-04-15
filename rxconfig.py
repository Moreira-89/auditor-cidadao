import reflex as rx

config = rx.Config(
    app_name="auditor_cidadao",
    plugins=[
        rx.plugins.SitemapPlugin(),
        rx.plugins.TailwindV4Plugin(),
    ]
)