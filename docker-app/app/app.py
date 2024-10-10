import os
import pandas as pd
import psycopg2
from flask import Flask

from dash import Dash, html, dcc, Input, Output, callback
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def select_from(table):
    with open("secrets.txt", "r") as file:
        creds = file.read().rstrip()

    try:
        with psycopg2.connect(creds) as conn:
            with conn.cursor() as cur:
                # execute the CREATE TABLE statement
                cur.execute(
                    f"""SELECT * FROM {table}
                            WHERE times > CURRENT_DATE - INTERVAL '14 day';"""
                )
                results = pd.DataFrame(cur.fetchall())
                print("results: ", results)
    except (psycopg2.DatabaseError, Exception) as error:
        print(error)

    return results[1], results[2], results[3]


@callback(
    Output("plots", "figure"),
    Input("interval-component", "n_intervals"),
)
def update_data(n):
    datetimes_inside, temps_inside, hums_inside = select_from("inside")
    datetimes_outside, temps_outside, hums_outside = select_from("outside")

    fig = make_subplots(
        rows=4,
        cols=4,
        shared_xaxes=True,
        vertical_spacing=0.05,
        specs=[
            [
                {"type": "indicator"},
                {"type": "scatter", "rowspan": 2, "colspan": 3},
                None,
                None,
            ],
            [{"type": "indicator"}, None, None, None],
            [
                {"type": "indicator"},
                {"type": "scatter", "rowspan": 2, "colspan": 3},
                None,
                None,
            ],
            [{"type": "indicator"}, None, None, None],
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
    fig.update_xaxes(title_text="Datetime", row=3, col=2)
    fig.update_layout(
        height=1000,
        template="plotly_dark",
        margin=dict(t=10, l=10, b=10, r=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
        ),
    )
    return fig


server = Flask(__name__)
app = Dash(server=server)

debug = False if os.environ["DASH_DEBUG_MODE"] == "False" else True

colors = {"background": "#111111", "text": "#7FDBFF"}

app.layout = html.Div(
    style={"backgroundColor": colors["background"]},
    children=[
        html.H1(
            children="Indoor/outdoor conditions for the past two weeks",
            style={"textAlign": "center", "color": colors["text"]},
        ),
        # html.Div(id="live-update-text"),
        dcc.Graph(id="plots"),
        dcc.Interval(
            id="interval-component",
            interval=300 * 1000,  # in milliseconds
            n_intervals=0,
        ),
    ],
)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port="8050", debug=debug)
