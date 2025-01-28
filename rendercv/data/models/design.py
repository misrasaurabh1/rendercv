"""
The `rendercv.data.models.design` module contains the data model of the `design` field
of the input file.
"""

import importlib
import importlib.util
import pathlib
from typing import Annotated, Any

import pydantic

from ...themes import (
    ClassicThemeOptions,
    EngineeringclassicThemeOptions,
    EngineeringresumesThemeOptions,
    ModerncvThemeOptions,
    Sb2novThemeOptions,
)
from . import entry_types
from .base import RenderCVBaseModelWithoutExtraKeys

# ======================================================================================
# Create validator functions: ==========================================================
# ======================================================================================


def validate_design_options(
    design: Any,
    available_theme_options: dict[str, type],
    available_entry_type_names: list[str],
) -> Any:
    """Check if the design options are for a built-in theme or a custom theme. If it is
    a built-in theme, validate it with the corresponding data model. If it is a custom
    theme, check if the necessary files are provided and validate it with the custom
    theme data model found in the `__init__.py` file of the custom theme folder.

    Args:
        design: The design options to validate.
        available_theme_options: The available theme options. The keys are the theme
            names and the values are the corresponding data models.
        available_entry_type_names: The available entry type names. These are used to
            validate if all the templates are provided in the custom theme folder.

    Returns:
        The validated design as a Pydantic data model.
    """
    from .rendercv_data_model import INPUT_FILE_DIRECTORY

    if isinstance(design, tuple(available_theme_options.values())):
        # Already validated built-in theme
        return design

    theme_name = design["theme"]
    if theme_name in available_theme_options:
        # Built-in theme, not validated yet
        ThemeDataModel = available_theme_options[theme_name]
        return ThemeDataModel(**design)

    # Custom theme validation
    if not theme_name.isalnum():
        raise ValueError(
            "The custom theme name should only contain letters and digits.",
            "theme",
            theme_name,
        )

    theme_parent_folder = (
        pathlib.Path(INPUT_FILE_DIRECTORY)
        if INPUT_FILE_DIRECTORY
        else pathlib.Path.cwd()
    )
    custom_theme_folder = theme_parent_folder / theme_name

    if not custom_theme_folder.exists():
        raise ValueError(
            f"The custom theme folder `{custom_theme_folder}` does not exist. It should"
            " be in the working directory as the input file.",
            "",
            theme_name,
        )

    required_files = [
        custom_theme_folder / "SectionBeginning.j2.typ",
        custom_theme_folder / "SectionEnding.j2.typ",
        custom_theme_folder / "Preamble.j2.typ",
        custom_theme_folder / "Header.j2.typ",
        *[
            custom_theme_folder / f"{entry_type_name}.j2.typ"
            for entry_type_name in available_entry_type_names
        ],
    ]

    missing_files = [str(file) for file in required_files if not file.exists()]
    if missing_files:
        raise ValueError(
            f"Missing files for custom theme: {', '.join(missing_files)} in folder"
            f" `{custom_theme_folder}`.",
            "",
            theme_name,
        )

    path_to_init_file = custom_theme_folder / "__init__.py"
    if path_to_init_file.exists():
        spec = importlib.util.spec_from_file_location("theme", path_to_init_file)
        theme_module = importlib.util.module_from_spec(spec)  # type: ignore
        try:
            spec.loader.exec_module(theme_module)  # type: ignore
        except (SyntaxError, ImportError) as e:
            raise ValueError(
                f"Error in the custom theme `{theme_name}`'s __init__.py file: {e}"
            )

        ThemeDataModel = getattr(theme_module, f"{theme_name.capitalize()}ThemeOptions")
        return ThemeDataModel(**design)

    # No __init__.py in the custom theme folder, creating a dummy data model
    class ThemeOptionsAreNotProvided(RenderCVBaseModelWithoutExtraKeys):
        theme: str = theme_name

    return ThemeOptionsAreNotProvided(theme=theme_name)


# ======================================================================================
# Create custom types: =================================================================
# ======================================================================================

available_theme_options = {
    "classic": ClassicThemeOptions,
    "sb2nov": Sb2novThemeOptions,
    "engineeringresumes": EngineeringresumesThemeOptions,
    "engineeringclassic": EngineeringclassicThemeOptions,
    "moderncv": ModerncvThemeOptions,
}

available_themes = list(available_theme_options.keys())

# Create a custom type named RenderCVBuiltinDesign:
# It is a union of all the design options and the correct design option is determined by
# the theme field, thanks to Pydantic's discriminator feature.
# See https://docs.pydantic.dev/2.7/concepts/fields/#discriminator for more information
RenderCVBuiltinDesign = Annotated[
    ClassicThemeOptions
    | Sb2novThemeOptions
    | EngineeringresumesThemeOptions
    | EngineeringclassicThemeOptions
    | ModerncvThemeOptions,
    pydantic.Field(discriminator="theme"),
]

# Create a custom type named RenderCVDesign:
# RenderCV supports custom themes as well. Therefore, `Any` type is used to allow custom
# themes. However, the JSON Schema generation is skipped, otherwise, the JSON Schema
# would accept any `design` field in the YAML input file.
RenderCVDesign = Annotated[
    pydantic.json_schema.SkipJsonSchema[Any] | RenderCVBuiltinDesign,
    pydantic.BeforeValidator(
        lambda design: validate_design_options(
            design,
            available_theme_options=available_theme_options,
            available_entry_type_names=entry_types.available_entry_type_names,  # type: ignore
        )
    ),
]
