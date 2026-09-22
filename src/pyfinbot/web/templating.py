from pathlib import Path

import greentechhub_ui
from fastapi.templating import Jinja2Templates
from jinja2 import ChoiceLoader, FileSystemLoader

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")
templates.env.loader = ChoiceLoader(
    [
        templates.env.loader,
        FileSystemLoader(greentechhub_ui.templates_path),
        FileSystemLoader(greentechhub_ui.components_path),
    ]
)

# greentechhub-ui shared shell context — see greentechhub-ui/docs/contract.md
templates.env.globals["brand"] = greentechhub_ui.theme.brand_context(service_name="PyFinBot")
templates.env.globals["nav_items"] = greentechhub_ui.navigation.build_nav_items(
    custom_items=[
        {"label": "Dashboard", "url": "/", "icon": "speedometer2"},
    ],
)
templates.env.globals["theme_css_url"] = "/gth-static/theme.css"
templates.env.globals["icons_css_url"] = "/gth-assets/icons/bootstrap-icons.min.css"
templates.env.globals["toast_js_url"] = "/gth-assets/js/toast.js"
templates.env.globals["show_theme_toggle"] = True
templates.env.globals["theme_toggle_js_url"] = "/gth-assets/js/theme-toggle.js"
