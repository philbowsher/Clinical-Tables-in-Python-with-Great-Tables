from shiny import App, ui, render, reactive
import pandas as pd
import numpy as np
from great_tables import GT
from great_tables.data import countrypops
from plotnine import (ggplot, aes, geom_line, theme_minimal, labs, 
                      scale_x_continuous, scale_y_continuous, theme,
                      element_text, element_rect, element_blank, element_line)

# Get the range of years available in the dataset
available_years = sorted(countrypops["year"].unique())
min_year = min(available_years)
max_year = max(available_years)

# Create a dictionary of country names and codes
country_codes = dict(zip(countrypops["country_name"], countrypops["country_code_3"]))

# Get the latest population data for sorting
latest_year = max(countrypops["year"])
latest_population = countrypops[countrypops["year"] == latest_year].set_index("country_name")["population"]

# Custom CSS for smaller, smallcaps-like labels and inline radio buttons
custom_css = """
    .control-label {
        font-size: 0.8em;
        font-weight: bold;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .radio-inline {
        display: inline-block;
        margin-right: 10px;
    }
    #countries {
        width: 200% !important;
    }
    h1 {
        margin-bottom: 30px;
    }
    #selection_message {
        display: inline-block;
        margin-left: 10px;
        color: #666;
        font-style: italic;
    }
"""

app_ui = ui.page_fluid(
    ui.tags.style(custom_css),
    ui.h1("Country Explorer"),
    ui.p(
        "This application allows you to explore and compare population data for different countries using World Bank population data. ",
        "You can select multiple countries, define a date range, and view the results in both tabular and graphical formats. ",
        "The application utilizes the Great Tables package for creating interactive tables and the plotnine package for generating beautiful plots."
    ),
    ui.p(
        ui.HTML(
            "Data source: World Bank Open Data (<a href='https://data.worldbank.org/' target='_blank'>https://data.worldbank.org/</a>)<br>"
            "Packages used: "
            "<a href='https://github.com/posit-dev/great-tables' target='_blank'>Great Tables</a>, "
            "<a href='https://github.com/has2k1/plotnine' target='_blank'>plotnine</a>"
        )
    ),
    ui.row(
        ui.column(3,
            ui.div(ui.strong("SORTING"), class_="control-label"),
            ui.input_radio_buttons(
                "sort_order",
                "",
                choices={
                    "largest": "Descending",
                    "smallest": "Ascending",
                    "alpha": "Alpha"
                },
                selected="largest",
                inline=True
            )
        ),
        ui.column(3,
            ui.div(ui.strong("START YEAR"), class_="control-label"),
            ui.input_select(
                "start_year",
                "",
                choices=[str(year) for year in available_years],
                selected=str(min_year),
                width="100px"
            ),
        ),
        ui.column(3,
            ui.div(ui.strong("END YEAR"), class_="control-label"),
            ui.input_select(
                "end_year",
                "",
                choices=[str(year) for year in available_years],
                selected=str(max_year),
                width="100px"
            ),
        ),
    ),
    ui.row(
        ui.column(12,
            ui.div(
                ui.div(ui.strong("SELECT COUNTRIES"), class_="control-label"),
                ui.input_selectize(
                    "countries",
                    "",
                    choices=[],  # We'll update this dynamically
                    multiple=True
                ),
                ui.output_text("selection_message", inline=True),
            ),
        ),
    ),
    ui.output_ui("population_table"),
    ui.output_plot("population_plot"),
)

def server(input, output, session):
    @reactive.Effect
    def _():
        countries = sorted(countrypops["country_name"].unique())
        if input.sort_order() == "largest":
            countries = sorted(countries, key=lambda x: latest_population.get(x, 0), reverse=True)
        elif input.sort_order() == "smallest":
            countries = sorted(countries, key=lambda x: latest_population.get(x, 0))
        ui.update_selectize("countries", choices=countries)

    @render.text
    def selection_message():
        if not input.countries():
            return "Please select at least one country."
        return ""

    @render.ui
    def population_table():
        if not input.countries():
            return ui.div()  # Return an empty div if no countries are selected

        country_data = countrypops[
            (countrypops["country_name"].isin(input.countries())) &
            (countrypops["year"] >= int(input.start_year())) &
            (countrypops["year"] <= int(input.end_year()))
        ]

        # Pivot the data to create separate columns for each country
        pivoted_data = country_data.pivot(index='year', columns='country_name', values='population').reset_index()
        pivoted_data.columns.name = None

        table = GT(pivoted_data)

        # Create the source note with country names and codes
        source_note = "Countries and associated codes: " + ", ".join([f"{country} ({country_codes[country]})" for country in input.countries()])

        if len(input.countries()) == 1:
            country = input.countries()[0]
            table = (
                table
                .cols_label(
                    year="Year",
                    **{country: "Population"}
                )
                .fmt_number(
                    columns=[country],
                    use_seps=True,
                    decimals=0
                )
                .tab_header(
                    title=f"{country}",
                    subtitle=f"Data from {input.start_year()} to {input.end_year()}"
                )
                .cols_width(
                    {
                        "year": "100px",
                        country: "130px"
                    }
                )
                .cols_align(align="center", columns="year")
                .tab_source_note(source_note=source_note)
            )
        else:
            table = (
                table
                .cols_label(year="Year")
                .fmt_number(
                    columns=list(input.countries()),
                    use_seps=True,
                    decimals=0
                )
                .tab_spanner(
                    label="Population",
                    columns=list(input.countries())
                )
                .tab_header(
                    title="Country Comparison",
                    subtitle=f"Data from {input.start_year()} to {input.end_year()}"
                )
                .cols_width(
                    {"year": "100px", **{col: "130px" for col in input.countries()}}
                )
                .cols_align(align="center", columns="year")
                .tab_source_note(source_note=source_note)
            )

        return table

    @render.plot
    def population_plot():
        if not input.countries():
            return None

        country_data = countrypops[
            (countrypops["country_name"].isin(input.countries())) &
            (countrypops["year"] >= int(input.start_year())) &
            (countrypops["year"] <= int(input.end_year()))
        ]

        def format_population(x):
            if isinstance(x, (list, np.ndarray)):
                return [format_population(val) for val in x]
            if x >= 1e6:
                return f'{x/1e6:.0f}M'
            elif x >= 1e3:
                return f'{x/1e3:.0f}K'
            else:
                return f'{x:.0f}'

        # Create the source note with country names and codes
        source_note = "Countries and associated codes: " + ", ".join([f"{country} ({country_codes[country]})" for country in input.countries()])

        plot = (
            ggplot(country_data, aes(x='year', y='population', color='country_name')) +
            geom_line() +
            theme_minimal() +
            labs(
                title='Population Time Series', 
                x='', 
                y='Population', 
                color='Country',
                caption=source_note
            ) +
            scale_x_continuous(breaks=range(int(input.start_year()), int(input.end_year()) + 1, 5)) +
            scale_y_continuous(labels=format_population) +
            theme(
                legend_position='right',
                plot_margin=0.15,
                axis_text_x=element_text(angle=0, hjust=0.5, size=8),
                figure_size=(11, 7),
                plot_background=element_rect(fill='white'),
                panel_background=element_rect(fill='white'),
                legend_box_margin=10,
                plot_title=element_text(hjust=0),  # Left-align the title
                axis_line=element_line(color='black', size=0.5),  # Add axis lines for left and bottom
                axis_line_x=element_line(color='black', size=0.5),
                axis_line_y=element_line(color='black', size=0.5),
                panel_grid_major=element_line(color='lightgray', size=0.5, linetype='dashed'),
                panel_grid_minor=element_blank(),
                plot_caption=element_text(hjust=0, size=8),  # Add caption styling
                panel_border=element_blank()  # Remove the outer box around the entire plot
            )
        )

        return plot

app = App(app_ui, server)