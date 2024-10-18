import os
import pandas as pd
import psycopg2
from flask import Flask
from datetime import datetime

from dash import Dash, html, dcc, Input, Output, callback, State
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def select_from(table):
    """Used for querying the specified server.

    Retrieves data from the server and filters out any unrealistic data points.

    Returns
    -------
    dateframe
        The dateframe containing datetime data.
    dateframe
        The dateframe containing temeprature data
    dateframe
        The dateframe containing humidity data.
    """
    with open("secrets.txt", "r") as file:
        creds = file.read().rstrip()

    try:
        with psycopg2.connect(creds) as conn:
            with conn.cursor() as cur:
                # execute the CREATE TABLE statement
                cur.execute(
                    f"""SELECT * FROM {table}
                            WHERE times > CURRENT_DATE - INTERVAL '14 day'
                            AND times > CAST('2024-10-05' AS DATE);"""
                )
                results = pd.DataFrame(cur.fetchall())
                print("results: ", results)
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

    results = results[results[2] > -50]
    results = results[results[2] < 100]
    results = results[results[3] >= 0]
    results = results[results[3] <= 100]

    return results[1], results[2], results[3]


@callback(
    Output("plots", "figure"),
    Input("interval-component", "n_intervals"),
)
def update_data(n):
    """Updates the data using the postgreSQL server.

    Queries the server for inside and outside datasets. Creates the figure that
    will be plotted on the server.

    Returns
    -------
    fig
        The plotly figure to plot
    """
    datetimes_inside, temps_inside, hums_inside = select_from("inside")
    datetimes_outside, temps_outside, hums_outside = select_from("outside")

    fig = make_subplots(
        rows=4,
        cols=5,
        shared_xaxes="all",
        vertical_spacing=0.05,
        specs=[
            [
                {"type": "indicator"},
                {"type": "scatter", "rowspan": 2, "colspan": 4},
                None,
                None,
                None,
            ],
            [{"type": "indicator"}, None, None, None, None],
            [
                {"type": "indicator"},
                {"type": "scatter", "rowspan": 2, "colspan": 4},
                None,
                None,
                None,
            ],
            [{"type": "indicator"}, None, None, None, None],
        ],
    )

    fig.add_trace(
        row=1,
        col=1,
        trace=go.Indicator(
            mode="number",
            value=temps_outside.max(),
            number={"suffix": "°C"},
            title={"text": "Outdoors Temperature Range"},
        ),
    )
    fig.add_trace(
        row=2,
        col=1,
        trace=go.Indicator(
            mode="number",
            value=temps_outside.min(),
            number={"suffix": "°C"},
        ),
    )
    fig.add_trace(
        row=3,
        col=1,
        trace=go.Indicator(
            mode="number",
            value=hums_outside.max(),
            number={"suffix": "%"},
            title={"text": "Outdoors Humidity Range"},
        ),
    )
    fig.add_trace(
        row=4,
        col=1,
        trace=go.Indicator(
            mode="number",
            value=hums_outside.min(),
            number={"suffix": "%"},
        ),
    )
    fig.add_trace(
        row=1,
        col=2,
        trace=go.Scatter(
            x=datetimes_inside,
            y=temps_inside,
            name="Inside Temperature",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=1,
        col=2,
        trace=go.Scatter(
            x=datetimes_outside,
            y=temps_outside,
            name="Outside Temperature",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=3,
        col=2,
        trace=go.Scatter(
            x=datetimes_inside,
            y=hums_inside,
            name="Inside Humidity",
            mode="lines+markers",
        ),
    )
    fig.add_trace(
        row=3,
        col=2,
        trace=go.Scatter(
            x=datetimes_outside,
            y=hums_outside,
            name="Outside Humidity",
            mode="lines+markers",
        ),
    )

    fig.update_yaxes(title_text="Temperature (°C)", row=1, col=2)
    fig.update_yaxes(title_text="Humidity (%)", range=[0, 100], row=3, col=2)
    fig.update_xaxes(
        title_text="Datetime",
        row=3,
        col=2,
    )
    fig.update_xaxes(
        row=1,
        col=2,
        rangeselector=dict(
            buttons=list(
                [
                    dict(count=1, label="1d", step="day", stepmode="backward"),
                    dict(count=2, label="2d", step="day", stepmode="backward"),
                    dict(count=7, label="7d", step="day", stepmode="backward"),
                    dict(step="all"),
                ]
            )
        ),
    )

    fig.update_layout(
        height=1000,
        template="plotly_dark",
        xaxis_rangeselector_font_color="black",
        xaxis_rangeselector_activecolor="grey",
        xaxis_rangeselector_bgcolor="darkgray",
        margin=dict(t=10, l=10, b=10, r=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    fig.update_layout(
        {
            "xaxis": {"matches": None},
            "xaxis2": {"matches": "x", "showticklabels": True},
        }
    )
    fig.update_layout(
        xaxis_range=[
            datetimes_inside.iloc[0] - pd.Timedelta(hours=1),
            datetimes_inside.iloc[-1] + pd.Timedelta(hours=1),
        ],
    )

    return fig


server = Flask(__name__)
app = Dash(server=server)

debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True

colors = {"background": "#111111", "text": "#7FDBFF"}

# app.layout = html.Div(
#     style={"backgroundColor": colors["background"]},
#     children=[
#         html.H1(
#             children="Indoor/outdoor conditions for the past two weeks",
#             style={"textAlign": "center", "color": colors["text"]},
#         ),
#         # html.Div(id="live-update-text"),
#         dcc.Graph(id="plots"),
#         dcc.Interval(
#             id="interval-component",
#             interval=15 * 60 * 1000,  # in milliseconds
#             n_intervals=0,
#         ),
#     ],
# )


app.layout = html.Div(
    [
        html.H1("Dash Tabs component demo"),
        dcc.Tabs(
            id="tabs-example-graph",
            value="tab-1-example-graph",
            children=[
                dcc.Tab(label="Tab One", value="tab-1-example-graph"),
                dcc.Tab(label="Tab Two", value="tab-2-example-graph"),
            ],
        ),
        html.Div(id="tabs-content-example-graph"),
        dcc.Interval(
            id="interval-component",
            interval=15 * 60 * 1000,  # in milliseconds
            n_intervals=0,
        ),
        html.Div(id="plots", style={"display": "none"}),
    ],
    style={"backgroundColor": colors["background"]},
)


@callback(
    Output("tabs-content-example-graph", "children"),
    Input("tabs-example-graph", "value"),
)
def render_content(tab):
    if tab == "tab-1-example-graph":
        return html.Div(
            [
                html.H3("Tab content 1"),
                dcc.Graph(id="plots"),
            ]
        )
    elif tab == "tab-2-example-graph":
        return html.Div(
            [
                html.H3("Tab content 2"),
                dcc.Graph(
                    id="graph-2-tabs-dcc",
                    figure={"data": [{"x": [1, 2, 3], "y": [5, 10, 6], "type": "bar"}]},
                ),
            ]
        )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8050", debug=debug)
