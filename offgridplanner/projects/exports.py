import io
from types import SimpleNamespace

import pandas as pd
from django.contrib.staticfiles.storage import staticfiles_storage
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Image
from reportlab.platypus import KeepTogether
from reportlab.platypus import ListFlowable
from reportlab.platypus import ListItem
from reportlab.platypus import PageBreak
from reportlab.platypus import Paragraph
from reportlab.platypus import SimpleDocTemplate
from reportlab.platypus import Spacer
from reportlab.platypus import Table
from reportlab.platypus import TableStyle


def format_first_col(df):
    df.iloc[:, 0] = (
        df.iloc[:, 0]
        .astype(str)
        .str.replace("shs", "SHS")
        .str.replace("_", " ")
        .str.capitalize()
        .str.replace("Mg", "Mini-grid")
        .str.replace("Lcoe", "LCOE")
        .str.replace("Pv", "PV")
        .str.replace(" dc ", " DC ")
        .str.replace("Co2", "CO2")
        .str.replace("Res", "RES share")
    )
    return df


def format_column_names(df):
    df.columns = [col.replace("_", " ").capitalize() for col in df.columns]
    return df


def prepare_data_for_export(  # noqa:PLR0913,PLR0915
    input_df, energy_system_design, energy_flow_df, results_df, nodes_df, links_df
):
    # TODO set units etc. with mapping instead
    """
    Prepares dataframes for export by formatting columns, adding units, and renaming fields.
    """

    # Merge input data and rename columns
    input_df["start_date"] = input_df["start_date"].dt.strftime("%m/%d/%Y, %H:%M:%S")
    input_df = pd.concat([input_df.T, energy_system_design.T])
    input_df.columns = ["User specified input parameters"]
    input_df.index.name = ""
    input_df = input_df.rename(
        index={"shs_max_grid_cost": "shs_max_specific_marginal_grid_cost"}
    )
    input_df["Unit"] = ""
    input_df.index.str.replace("_parameters_", "_parameter: ")
    input_df.index.str.replace("_settings_", "_settings: ")
    input_df.loc["n_days", "Unit"] = "days"
    input_df.loc["interest_rate", "Unit"] = "%"
    input_df.loc[
        ["distribution_cable_capex", "pole_capex", "connection_cable_capex"], "Unit"
    ] = "USD/m"
    input_df.loc[input_df.index.str.contains("lifetime"), "Unit"] = "years"
    input_df.loc[input_df.index.str.contains("length"), "Unit"] = "m"
    input_df.loc[input_df.index.str.contains("_capex"), "Unit"] = "USD/kWh"
    input_df.loc[input_df.index.str.contains("_opex"), "Unit"] = "USD/(kW a)"
    input_df.loc[input_df.index.str.contains("_fuel"), "Unit"] = "USD/l"
    input_df.loc[input_df.index.str.contains("_fuel_cost"), "Unit"] = "USD/l"
    input_df.loc[input_df.index.str.contains("_fuel_lhv"), "Unit"] = "kWh/kg"
    input_df.loc[input_df.index.str.contains("_capacity"), "Unit"] = "kWh"
    input_df.loc[["battery_parameters_capex"], "Unit"] = "USD/kWh"
    input_df.loc[["mg_connection_cost"], "Unit"] = "USD"
    input_df.loc[["shs_max_specific_marginal_grid_cost"], "Unit"] = "c/kWh"
    input_df = input_df.reset_index()
    input_df = format_first_col(input_df)
    cols = [
        col.replace("_", " ").capitalize() + " [kW]"
        if "content" not in col
        else col.replace("_", " ").capitalize() + " [kWh]"
        for col in energy_flow_df.columns
    ]
    energy_flow_df.columns = cols
    energy_flow_df = energy_flow_df.reset_index()
    results_df = results_df.T.reset_index()
    results_df["Unit"] = ""
    results_df.columns = ["", "Value", "Unit"]
    results_df = format_first_col(results_df)
    results_df = results_df.set_index("")
    results_df.loc[results_df.index.str.contains("length"), "Unit"] = "m"
    results_df.loc[results_df.index.str.contains("CO2"), "Unit"] = "t/a"
    results_df.loc[results_df.index.str.contains("Upfront"), "Unit"] = "USD"
    results_df.loc[results_df.index.str.contains("Cost"), "Unit"] = "USD/a"
    results_df.loc[results_df.index.str.contains("Epc"), "Unit"] = "USD/a"
    results_df.loc[results_df.index.str.contains("capacity"), "Unit"] = "USD/kW"
    results_df.loc[["Battery capacity"], "Unit"] = "USD/kWh"
    results_df.loc[
        [
            "Max voltage drop",
            "RES share",
            "Surplus rate",
            "Shortage total",
            "Max shortage",
        ],
        "Unit",
    ] = "%"
    results_df.loc[
        [
            "Average annual demand per consumer",
            "Fuel consumption",
            "Total annual consumption",
            "Surplus",
        ],
        "Unit",
    ] = "kWh/a"
    results_df = results_df[~results_df.index.str.contains("Time")]
    results_df = results_df[~results_df.index.str.contains(" to ")]
    results_df.loc[["LCOE"], "Unit"] = "c/kWh"
    results_df.loc[["Base load", "Peak demand"], "Unit"] = "kW"
    results_df = results_df.T
    results_df = results_df.T.reset_index()
    for col in ["distribution_cost", "parent"]:
        if col in nodes_df.columns:
            nodes_df = nodes_df.drop(columns=[col])
    nodes_df = format_column_names(nodes_df)
    links_df = (
        links_df[["link_type", "length", "lat_from", "lon_from", "lat_to", "lon_to"]]
        if not links_df.empty
        else links_df
    )
    links_df = format_column_names(links_df)
    return input_df, energy_flow_df, results_df, nodes_df, links_df


def load_reportlab_styles():
    styles = getSampleStyleSheet()
    subtitle_style = ParagraphStyle(
        "Subtitle",
        parent=styles["Title"],  # Changed to an existing style
        fontSize=14,
        alignment=TA_CENTER,
        spaceAfter=24,
        leading=28,
    )
    body_style = ParagraphStyle(
        "BodyText",
        parent=styles["BodyText"],
        fontSize=12,
        alignment=TA_JUSTIFY,
        leading=26,
        spaceAfter=12,
    )
    toc_title_style = ParagraphStyle(
        "toc_title",
        parent=styles["Title"],
        fontSize=16,
        alignment=TA_LEFT,
        spaceAfter=6,
    )
    """
    table_style = TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),  # Left-align section titles
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Right-align page numbers
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),  # Bold font for header row
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),  # Regular font for other rows
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
        # Add a horizontal line below the header row
        ('LINEBELOW', (0, 0), (-1, 0), 1, colors.black),
    ])
    """
    table_style = TableStyle(
        [
            # Top line above header
            ("LINEABOVE", (0, 0), (-1, 0), 1, "BLACK"),
            # Bottom line below header (midrule)
            ("LINEBELOW", (0, 0), (-1, 0), 1, "BLACK"),
            # Bottom line below the last row
            ("LINEBELOW", (0, -1), (-1, -1), 1, "BLACK"),
            # Alignment:
            ("ALIGN", (0, 0), (0, -1), "LEFT"),  # First column left-aligned
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),  # Second column right-aligned
            ("ALIGN", (2, 0), (2, -1), "RIGHT"),  # Third column right-aligned
            # Padding
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]
    )

    header_style = ParagraphStyle(
        "Header",
        parent=styles["Heading4"],
        fontSize=12,
        alignment=TA_JUSTIFY,
        spaceAfter=6,
        leading=14,
    )
    italic_body_style = ParagraphStyle(
        name="ItalicBody",
        parent=getSampleStyleSheet()["BodyText"],  # Inherit from 'BodyText' style
        fontName="Helvetica-Oblique",  # Use an italic variant of Helvetica
        fontSize=10,
        leading=12,  # Optional: Adjust line spacing as needed
        alignment=TA_JUSTIFY,  # Left-aligned text
    )

    def add_page_number(canvas, doc):
        """
        Adds the page number at the bottom right of the page.
        Page numbering starts at 1 from the second page.
        """
        page_num = doc.page
        if page_num > 1:
            display_num = page_num - 1
            text = f"Page {display_num}"
            canvas.setFont("Helvetica", 9)
            x_position = 185 * mm
            y_position = 15 * mm
            canvas.drawRightString(x_position, y_position, text)

    def on_first_page(canvas, doc):
        """
        No operation function for the first page.
        """

    return (
        styles,
        subtitle_style,
        body_style,
        toc_title_style,
        table_style,
        header_style,
        italic_body_style,
        add_page_number,
        on_first_page,
    )


# TODO refactor export functions
def create_pdf_report(  # noqa: PLR0915, PLR0912, C901
    img_dict, dataframes
):
    """
    Generates a PDF report based on the provided data and images.

    Parameters:
        img_dict (dict): Dictionary containing image objects.
        dataframes (dict): Dict of dataframes containing project data.

    Returns:
        tuple: A tuple containing the PDF document object and a BytesIO buffer.
    """

    energy_flow_df = dataframes["energy_flow_df"]
    input_df = dataframes["input_parameters_df"]
    results_df = dataframes["results_df"]
    energy_system_design = dataframes["energy_system_design_df"]
    nodes_df = dataframes["nodes_df"]
    links_df = dataframes["links_df"]
    custom_demand_df = dataframes["custom_demand_df"]

    # Prepare data (assuming this function is defined elsewhere)
    demand_ts = energy_flow_df["demand"].copy()
    input_df, energy_flow_df, results_df, nodes_df, links_df = prepare_data_for_export(
        input_df, energy_system_design, energy_flow_df, results_df, nodes_df, links_df
    )

    # Convert DataFrames to SimpleNamespace for easier attribute access
    input_data = SimpleNamespace(
        **dict(
            zip(
                input_df.iloc[:, 0].str.replace(" ", "_").str.lower(),
                input_df.iloc[:, 1],
                strict=False,
            )
        )
    )

    results = SimpleNamespace(
        **dict(
            zip(
                results_df.iloc[:, 0].str.replace(" ", "_").str.lower(),
                results_df.iloc[:, 1],
                strict=False,
            )
        )
    )

    # Load ReportLab styles
    (
        styles,
        subtitle_style,
        body_style,
        toc_title_style,
        table_style,
        header_style,
        italic_body_style,
        add_page_number,
        on_first_page,
    ) = load_reportlab_styles()

    # Initialize PDF elements list
    elements = []

    # Add logo and titles
    image_path = staticfiles_storage.path("assets/logos/LogoFUNAE.svg")
    image_reader = ImageReader(image_path)
    img_width, img_height = image_reader.getSize()
    desired_height = 1 * inch  # Adjust as needed
    desired_width = desired_height * img_width / img_height
    logo = Image(image_path, width=desired_width, height=desired_height)
    logo.hAlign = "LEFT"

    title = Paragraph("Off-Grid System Planning Results", styles["Title"])
    subtitle = Paragraph(
        "Energy System Optimization Carried Out with the Tool Offgridplanner (https://offgridplanner.org)",
        subtitle_style,
    )

    elements.append(
        KeepTogether(
            [
                logo,
                Spacer(1, 12),  # Space between logo and title
                title,
                subtitle,
                Spacer(1, 12),
            ]
        )
    )

    # Add project details
    elements.append(Paragraph(f"Project Name: {input_data.name}", body_style))
    elements.append(
        Paragraph(f"Project Description: {input_data.description}", body_style)
    )

    # Add Table of Contents
    elements.append(Spacer(1, 48))
    elements.append(Paragraph("Table of Contents", toc_title_style))
    elements.append(Spacer(1, 12))

    toc = [
        ["Section", "Page"],
        ["1. Overview of Project Parameters", "&nbsp;&nbsp;1"],
        ["2. Brief Tool Description", "&nbsp;&nbsp;2"],
    ]

    planning_steps = []

    # Demand Estimation Step
    if input_data.do_demand_estimation:
        planning_steps.append("Demand estimation based on selected consumers")
        toc.append(["3. Demand Estimation", "&nbsp;&nbsp;4"])
    else:
        toc.append(["3. Demand Time Series", "&nbsp;&nbsp;4"])

    # Grid Optimization Step
    if input_data.do_grid_optimization:
        grid_text = "Spatial optimization of distribution grid"
        grid_text += f" with the option to exclude consumers with specific marginal connection costs above {input_data.shs_max_specific_marginal_grid_cost} c/kWh"
        planning_steps.append(grid_text)
        toc.append(["4. Optimal Spatial Distribution of the Grid", "&nbsp;&nbsp;5"])

    # Energy System Design Optimization Step
    if input_data.do_es_design_optimization:
        planning_steps.append("Design optimization of energy converters and storage")
        pos = 5 if input_data.do_grid_optimization else 4
        page = 6 if input_data.do_grid_optimization else 5
        toc.append(
            [
                f"{pos}. Optimal Design of Energy Converters and Storage",
                f"&nbsp;&nbsp;{page}",
            ]
        )

    if input_data.do_es_design_optimization:
        page = 5
        if input_data.do_grid_optimization:
            page += 1
        if input_data.do_es_design_optimization:
            page += 4
        pos = (
            6
            if input_data.do_es_design_optimization and input_data.do_grid_optimization
            else 5
        )
        toc.append([f"{pos}. Overview of Economic Results", f"&nbsp;&nbsp;{page}"])

    # Create ToC entries
    toc_entries = []
    left_margin = right_margin = 72  # 1 inch margins
    max_table_width = A4[0] - left_margin - right_margin  # A4 width minus margins
    page_number_width = 50  # Width reserved for page numbers

    for section, page in toc:
        section_para = Paragraph(f"<b>{section}</b>", header_style)
        page_para = Paragraph(f"<b>{page}</b>", header_style)
        toc_entries.append([section_para, page_para])

    # Define column widths
    col_widths = [
        max_table_width - page_number_width,  # First column width (section titles)
        page_number_width,  # Second column width (page numbers)
    ]

    # Create ToC Table
    toc_table = Table(toc_entries, colWidths=col_widths)
    toc_table.setStyle(table_style)
    elements.append(toc_table)

    # Add Page Break
    elements.append(PageBreak())

    # Section 1: Overview of Project Parameters
    elements.append(Paragraph("1. Overview of Project Parameters", styles["Heading1"]))
    elements.append(Spacer(1, 24))

    if not nodes_df.empty:
        latitude = nodes_df["Latitude"].median().round(4)
        longitude = nodes_df["Longitude"].median().round(4)

        overview_text = (
            f"For the location at latitude {latitude}° and longitude {longitude}° with {results.n_consumers} selected consumers, "
            "the following planning steps were carried out:"
        )
    else:
        overview_text = "The following planning steps were carried out:"
    elements.append(Paragraph(overview_text, body_style))

    # Create Planning Steps List
    planning_steps_flowable = ListFlowable(
        [
            ListItem(Paragraph(step, body_style), leftIndent=20)
            for step in planning_steps
        ],
        bulletType="bullet",
        spaceBefore=12,
        spaceAfter=12,
        bulletFontName="Helvetica",
        bulletFontSize=12,
        bulletColor="black",
    )
    elements.append(planning_steps_flowable)

    # Economic Assessment Text
    economic_assessment_text = (
        f"For the economic assessment, a project duration of {input_data.lifetime} years and an interest rate of "
        f"{input_data.interest_rate}% have been applied."
    )
    if input_data.do_es_design_optimization:
        economic_assessment_text += (
            " The design optimization of the energy converters and storage is based on a unit commitment carried out for a period "
            f"of {input_data.n_days} days. The operating costs resulting from this period are scaled up to the project's lifetime, "
            "taking into account the time value of money according to the specified interest rate."
        )
    elements.append(Paragraph(economic_assessment_text, body_style))

    # Add Spacer
    elements.append(PageBreak())

    # Section 2: Brief Tool Description
    elements.append(Paragraph("2. Brief Tool Description", styles["Heading1"]))
    elements.append(Spacer(1, 24))

    # Add Tool Description Paragraphs
    elements.append(
        Paragraph(
            "The tool systematically integrates geospatial data, demand forecasting, grid optimization, and generation system design to deliver optimized energy solutions. "
            "It begins by acquiring geolocation data of consumers through automatic detection using OpenStreetMap integration, manual selection via map markers, or direct input of geocoordinates. "
            "This geospatial information forms the foundation for demand estimation and grid layout planning.",
            body_style,
        )
    )
    elements.append(
        Paragraph(
            "For demand estimation, the tool employs statistical models and stochastic algorithms based on extensive survey data from thousands of households and enterprises in non-urban Nigerian villages. "
            "It analyzes factors such as appliance ownership, electricity consumption patterns, and affordability to generate realistic demand profiles. "
            "These profiles are customized for each location, considering geographical zones and socioeconomic levels, to provide precise predictions of electricity demand.",
            body_style,
        )
    )
    elements.append(
        Paragraph(
            "With both geolocation and demand data, the tool optimizes the spatial layout of the distribution grid. "
            "It sorts consumers based on proximity to the load center and determines optimal pole locations using clustering algorithms. "
            "A minimum spanning tree is constructed to ensure efficient interconnectivity between poles. "
            "The tool adheres to constraints on maximum connections per pole and maximum distances between consumers, "
            "adding additional poles or segmenting long connections as necessary to ensure all consumers are effectively connected.",
            body_style,
        )
    )
    elements.append(
        Paragraph(
            "In the generation system design phase, the tool integrates various energy converters, including photovoltaic systems and diesel generators, "
            "along with battery storage, inverters, and rectifiers. It models solar potential using ERA5 satellite data and PVLIB software. "
            "The optimization focuses on minimizing the Levelized Cost of Energy (LCOE) by considering both capital expenditures and operational costs. "
            "Formulating the problem as a mixed-integer linear model, the tool utilizes the open-source modeling framework OEMOF and the high-performance Gurobi solver "
            "to find the optimal configuration that meets consumer demands.",
            body_style,
        )
    )
    elements.append(
        Paragraph(
            "Finally, the tool provides detailed outputs such as optimal installed capacities for each system component, time-series data of system operations, "
            "investment cost breakdowns, CO<sub>2</sub> emission estimates, and fuel consumption requirements. "
            "These results offer valuable insights for stakeholders to make informed decisions regarding the planning and implementation of off-grid energy solutions.",
            body_style,
        )
    )

    # Add Page Break
    elements.append(PageBreak())

    # Section 3: Demand Estimation
    elements.append(Paragraph(toc[3][0], styles["Heading1"]))
    elements.append(Spacer(1, 24))

    # Helper function for pluralization
    def pluralize(count, singular, plural):
        return singular if count == 1 else plural

    # Determine if custom demand was used
    # import pdb; pdb.set_trace()
    if custom_demand_df.iloc[0].uploaded_data:
        elements.append(
            Paragraph(
                "The demand estimation feature of the tool was not used. Instead, a time series was uploaded by the user.",
                body_style,
            )
        )
        demand_ts = custom_demand_df.iloc[:, 0]
    else:
        # Count different types of consumers
        consumers_df = nodes_df[nodes_df["Node type"] == "consumer"]
        n_households = consumers_df[consumers_df["Consumer type"] == "household"].shape[
            0
        ]
        n_enterprises = consumers_df[
            consumers_df["Consumer type"] == "enterprise"
        ].shape[0]
        n_public_services = consumers_df[
            consumers_df["Consumer type"] == "public_service"
        ].shape[0]

        # Add consumer counts
        elements.append(
            Paragraph(
                f"A total of {n_households} {pluralize(n_households, 'household', 'households')}, "
                f"{n_enterprises} {pluralize(n_enterprises, 'enterprise', 'enterprises')}, and "
                f"{n_public_services} {pluralize(n_public_services, 'public service', 'public services')} were selected.",
                body_style,
            )
        )

        if "demand" in energy_flow_df.columns:
            demand_ts = energy_flow_df["demand"]

    # Calculate yearly demand
    yearly_demand = demand_ts.sum()
    num_hours = demand_ts.shape[0]
    full_year_hours = 8760

    # Add demand statistics
    demand_text = (
        f"The demand time series has a maximum load of {demand_ts.max():.2f} kW, "
        f"a minimum load of {demand_ts.min():.2f} kW, and an average load of {demand_ts.mean():.2f} kW. "
        f"The total annual demand is estimated to be {yearly_demand:.0f} kWh."
    )
    if num_hours < full_year_hours:
        demand_text += (
            f" Note: The original demand time series covered {num_hours} hours and has been scaled up "
            f"to represent a full year (8760 hours) for annual demand estimation."
        )
    elements.append(Paragraph(demand_text, body_style))

    # Insert image and caption if demand estimation was performed
    if not custom_demand_df.iloc[0].uploaded_data and input_data.do_demand_estimation:
        elements.append(img_dict.get("demandTs"))
        elements.append(
            Paragraph(
                "Figure: Demand Coverage of the Off-Grid System",
                ParagraphStyle(
                    "FigureCaption",
                    fontSize=8,
                    alignment=1,  # TA_CENTER
                    spaceAfter=24,
                    fontName="Helvetica-Oblique",
                ),
            )
        )
    elements.append(PageBreak())
    if input_data.do_grid_optimization:
        # Section 4: Optimal Spatial Distribution of the Grid
        elements.append(Paragraph(toc[4][0], styles["Heading1"]))
        elements.append(Spacer(1, 24))
        # Add distribution grid map
        elements.append(img_dict.get("map"))
        elements.append(
            Paragraph(
                "Figure: Distribution Grid of the Off-Grid System",
                ParagraphStyle(
                    "FigureCaption",
                    fontSize=8,
                    alignment=1,  # TA_CENTER
                    spaceAfter=24,
                    fontName="Helvetica-Oblique",
                ),
            )
        )

        # Add connection details
        connected_text = f"Out of the total {results.n_consumers} selected consumers, "
        if results.n_shs_consumers == 0:
            connected_text += "all were connected to the grid."
        else:
            num_unconnected = results.n_shs_consumers
            consumer_word = "consumer" if num_unconnected == 1 else "consumers"
            threshold = input_data.shs_max_specific_marginal_grid_cost
            connected_text += (
                f"{num_unconnected} {consumer_word} were not connected to the grid because their specific marginal connection costs exceeded "
                f"the user-defined threshold of {threshold} c/kWh. Therefore, these consumers will need to be equipped with a solar home system "
                "instead."
            )
        elements.append(Paragraph(connected_text, body_style))

        # Add grid requirements
        grid_requirements_text = (
            f"The grid requires {results.n_poles} poles, {results.length_distribution_cable} meters of distribution cable, and "
            f"{results.length_connection_cable} meters of connection cable. The upfront grid investment costs amount to "
            f"{results.upfront_invest_grid:,.0f} USD."
        )
        elements.append(Paragraph(grid_requirements_text, body_style))

        # Add positioning details
        positioning_text = (
            "The positioning of the poles and the layout of the connection cables are shown on the attached map. Detailed location "
            "information, including latitude and longitude values, can be found in the Excel file."
        )
        elements.append(Paragraph(positioning_text, body_style))

        # Add Page Break
        elements.append(PageBreak())

    # Section 5: Optimal Design of Energy Converters and Storage
    if input_data.do_es_design_optimization:
        elements.append(Paragraph(toc[-2][0], styles["Heading1"]))
        elements.append(Spacer(1, 24))

        # Introduction to energy design
        energy_design_intro = "The minimization of the project's total costs during project lifetime results in the following installations:"
        elements.append(Paragraph(energy_design_intro, body_style))

        # Create capacity dictionary
        capacity_dict = {}
        if results.pv_capacity > 0:
            capacity_dict["PV"] = f"{results.pv_capacity:,.1f} kW"
        if results.diesel_genset_capacity > 0:
            capacity_dict["Diesel Generator"] = (
                f"{results.diesel_genset_capacity:,.1f} kW"
            )
        if results.inverter_capacity > 0:
            capacity_dict["Inverter"] = f"{results.inverter_capacity:,.1f} kW"
        if results.rectifier_capacity > 0:
            capacity_dict["Rectifier"] = f"{results.rectifier_capacity:,.1f} kW"
        if results.battery_capacity:
            capacity_dict["Battery System"] = (
                f"{results.battery_capacity:,.1f} kWh"  # Corrected typo
            )

        # Define table headers
        table_data = [["Unit", "Capacity"]]
        for unit, capacity in capacity_dict.items():
            table_data.append([unit, capacity])

        # Create capacity table
        capacity_table = Table(table_data, colWidths=[250, 150])
        capacity_table.setStyle(table_style)
        elements.append(capacity_table)
        elements.append(Spacer(1, 24))

        # System performance text
        system_performance_text = (
            f"With this system, a renewable energy share of {results.res_share:.1f}% is achieved. "
            f"An electricity surplus of {results.surplus_rate:.1f}% occurs. "
        )
        if results.shortage_total == 0:
            system_performance_text += "The demand is met at all times."
        else:
            system_performance_text += (
                f"The demand is not fully met at all times; the shortage amounts to {results.shortage_total:.1f}%. "
                "Note: Designing the energy system without accounting for maximum load peaks can lead to significant cost savings, "
                "but it may compromise grid stability."
            )
        elements.append(Paragraph(system_performance_text, body_style))

        # Add Sankey Diagram
        sankey_text = "The presented Sankey diagram visualizes the extent to which each component contributes to meeting the demand."
        elements.append(Paragraph(sankey_text, body_style))
        elements.append(img_dict.get("sankeyDiagram"))
        elements.append(
            Paragraph(
                "Figure: Sankey Diagram Representing the Energy Flow in the System",
                ParagraphStyle(
                    "FigureCaption",
                    fontSize=8,
                    alignment=1,  # TA_CENTER
                    spaceAfter=24,
                    fontName="Helvetica-Oblique",
                ),
            )
        )

        # Additional Diagrams
        additional_diagrams_text = (
            "The following two diagrams illustrate an exemplary period at the beginning of the simulation timeframe, "
            "depicting the system's demand coverage and energy flows."
        )
        elements.append(Paragraph(additional_diagrams_text, body_style))

        elements.append(img_dict.get("demandCoverage"))
        elements.append(
            Paragraph(
                "Figure: Range by Renewable and Non-Renewable Resources",
                ParagraphStyle(
                    "FigureCaption",
                    fontSize=8,
                    alignment=1,  # TA_CENTER
                    spaceAfter=24,
                    fontName="Helvetica-Oblique",
                ),
            )
        )

        elements.append(img_dict.get("energyFlows"))
        elements.append(
            Paragraph(
                "Figure: Energy Flows with 1-Hour Resolution",
                ParagraphStyle(
                    "FigureCaption",
                    fontSize=8,
                    alignment=1,  # TA_CENTER
                    spaceAfter=24,
                    fontName="Helvetica-Oblique",
                ),
            )
        )

        # Add Page Break
        elements.append(PageBreak())

    # Section 6: Overview of Economic Results
    if input_data.do_es_design_optimization:
        elements.append(Paragraph(toc[-1][0], styles["Heading1"]))
        elements.append(Spacer(1, 24))

        # Calculate investment costs
        upfront_invest_total = results_df[
            results_df.iloc[:, 0].str.contains("Upfront")
        ]["Value"].sum()
        upfront_invest_converters_and_storage = (
            upfront_invest_total - results.upfront_invest_grid
        )

        # Add investment costs text
        economic_costs_text = (
            f"The total upfront investment costs amount to {upfront_invest_total:,.0f} USD. "
            f"Of this, {results.upfront_invest_grid:,.0f} USD is allocated to grid investment costs, and "
            f"{upfront_invest_converters_and_storage:,.0f} USD is allocated to energy converters and battery systems."
        )
        elements.append(Paragraph(economic_costs_text, body_style))

        # Add LCOE text
        if input_data.do_es_design_optimization:
            lcoe_text = f"The Levelized Cost of Electricity for the energy system is {results.lcoe:,.0f} cents per kWh."
            elements.append(Paragraph(lcoe_text, body_style))

            # Add LCOE Breakdown Image
            elements.append(img_dict.get("lcoeBreakdown"))
            elements.append(
                Paragraph(
                    "Figure: Levelized Cost of Electricity Breakdown",
                    ParagraphStyle(
                        "FigureCaption",
                        fontSize=8,
                        alignment=1,  # TA_CENTER
                        spaceAfter=24,
                        fontName="Helvetica-Oblique",
                    ),
                )
            )

        # Add Page Break
        elements.append(PageBreak())

        # Add economic details table
        economic_details_text = (
            "The following table lists the respective upfront investment costs of individual components of the energy system, as well as "
            "the annualized costs."
        )
        elements.append(Paragraph(economic_details_text, body_style))

        table_data = [
            [
                "Component of Energy System",
                "Upfront Investment Costs",
                "Annualized Costs",
            ],
        ]
        if input_data.do_grid_optimization:
            table_data.append(
                [
                    "Grid",
                    f"{results.upfront_invest_grid:,.0f} USD",
                    f"{results.cost_grid:,.0f} USD",
                ]
            )
        if input_data.do_es_design_optimization:
            table_data += [
                [
                    "PV",
                    f"{results.upfront_invest_pv:,.0f} USD",
                    f"{results.epc_pv:,.0f} USD",
                ],
                [
                    "Diesel Genset",
                    f"{results.upfront_invest_diesel_genset:,.0f} USD",
                    f"{results.epc_diesel_genset:,.0f} USD",
                ],
                [
                    "Inverter",
                    f"{results.upfront_invest_inverter:,.0f} USD",
                    f"{results.epc_inverter:,.0f} USD",
                ],
                [
                    "Rectifier",
                    f"{results.upfront_invest_rectifier:,.0f} USD",
                    f"{results.epc_rectifier:,.0f} USD",
                ],
                [
                    "Battery",
                    f"{results.upfront_invest_battery:,.0f} USD",
                    f"{results.epc_battery:,.0f} USD",
                ],
                ["Diesel Fuel", "-", f"{results.cost_fuel:,.0f} USD"],
            ]
        if input_data.do_grid_optimization and input_data.do_es_design_optimization:
            table_data.append(
                [
                    "Total",
                    f"{upfront_invest_total:,.0f} USD",
                    f"{results.epc_total:,.0f} USD",
                ]
            )

        economic_table = Table(table_data, colWidths=[200, 100, 100])
        economic_table.setStyle(table_style)
        elements.append(economic_table)
        elements.append(Spacer(1, 24))

        if input_data.do_grid_optimization and input_data.do_es_design_optimization:
            # Add Note on Annualized Costs
            note_text = (
                "Note: Annualized costs provide a comprehensive view of the expenses related to an investment over its duration. These costs include the initial investment expenses, "
                "the costs for replacing assets with a lifespan shorter than the project, variable costs, fuel expenses, and the residual value at the end of the project's lifecycle. "
                "By incorporating the time value of money using a specified interest rate, annualized costs translate these multifaceted expenditures into a standardized yearly figure. "
                "The Capital Recovery Factor (CRF) is utilized in the calculation to ensure a consistent and accurate understanding of the total costs over time."
            )
            elements.append(Paragraph(note_text, italic_body_style))

    # Build the PDF document
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4, leftMargin=left_margin, rightMargin=right_margin
    )
    doc.title = "Offgridplanner"
    doc.author = "PeopleSuN"
    doc.subject = f"{input_data.name}"
    doc.keywords = "off-grid, energy, planning"

    doc.build(elements, onFirstPage=on_first_page, onLaterPages=add_page_number)
    buffer.seek(0)
    return doc, buffer


def project_data_df_to_xlsx(  # noqa:PLR0913
    input_df, energy_system_design, energy_flow_df, results_df, nodes_df, links_df
):
    input_df, energy_flow_df, results_df, nodes_df, links_df = prepare_data_for_export(
        input_df, energy_system_design, energy_flow_df, results_df, nodes_df, links_df
    )
    excel_file = io.BytesIO()
    with pd.ExcelWriter(excel_file, engine="xlsxwriter") as writer:
        workbook = writer.book
        sheet1 = "results"
        results_df.to_excel(writer, sheet_name=sheet1, index=False)
        worksheet1 = writer.sheets[sheet1]
        format1 = workbook.add_format({"align": "left"})
        format2 = workbook.add_format({"align": "right"})
        col1_width = results_df.iloc[:, 0].astype(str).str.len().max()
        col2_width = results_df.iloc[:, 1].astype(str).str.len().max()
        col3_width = results_df.iloc[:, 2].astype(str).str.len().max()
        worksheet1.set_column(0, 0, col1_width, format1)
        worksheet1.set_column(1, 1, col2_width, format2)
        worksheet1.set_column(2, 2, col3_width, format1)
        sheet2 = "power time series"
        energy_flow_df.to_excel(writer, sheet_name=sheet2, index=False)
        writer.sheets[sheet2] = set_column_width(
            writer.sheets[sheet2],
            energy_flow_df,
            workbook.add_format({"align": "right"}),
        )
        sheet3 = "user specified input parameters"
        input_df.to_excel(writer, sheet_name=sheet3, index=False)
        worksheet3 = writer.sheets[sheet3]
        format1 = workbook.add_format({"align": "left"})
        format2 = workbook.add_format({"align": "right"})
        col1_width = input_df.iloc[:, 0].astype(str).str.len().max()
        col2_width = input_df.iloc[:, 1].astype(str).str.len().max()
        col3_width = input_df.iloc[:, 2].astype(str).str.len().max()
        worksheet3.set_column(0, 0, col1_width, format1)
        worksheet3.set_column(1, 1, col2_width, format2)
        worksheet3.set_column(2, 2, col3_width, format1)
        sheet4 = "nodes"
        nodes_df.to_excel(writer, sheet_name=sheet4, index=False)
        writer.sheets[sheet4] = set_column_width(
            writer.sheets[sheet4], nodes_df, workbook.add_format({"align": "right"})
        )
        sheet5 = "links"
        links_df.to_excel(writer, sheet_name=sheet5, index=False)
        writer.sheets[sheet5] = set_column_width(
            writer.sheets[sheet5], links_df, workbook.add_format({"align": "right"})
        )
    xlsx_data = excel_file.getvalue()
    return io.BytesIO(xlsx_data)


def set_column_width(worksheet, df, col_format=None):
    for i, col in enumerate(df.columns):
        column_len = df[col].astype(str).str.len().max()
        column_len = max(column_len, len(col)) + 2
        column_len = min(column_len, 150)
        if col_format:
            worksheet.set_column(i, i, column_len, col_format)
        else:
            worksheet.set_column(i, i, column_len)
    return worksheet
